"""Bounded RSS/Atom preview for the hosted filtered-firehose concept.

This module deliberately stops at an instant preview. It does not persist
sources, schedule future runs, call an LLM, or deliver email. Network fetches
are limited and reject non-public destinations before every redirect.
"""
from __future__ import annotations

import html
import http.client
import ipaddress
import re
import socket
import urllib.parse
from collections import Counter
from collections.abc import Callable
from html.parser import HTMLParser
from typing import Any
from xml.etree import ElementTree

MAX_REQUEST_BYTES = 24 * 1024
MAX_SOURCES = 6
MAX_SOURCE_URL_CHARS = 2048
MAX_FOCUS_CHARS = 500
MAX_IGNORE_TERMS = 20
MAX_IGNORE_TERM_CHARS = 100
MAX_FEED_BYTES = 1024 * 1024
MAX_PARSED_ITEMS_PER_SOURCE = 50
MAX_PREVIEW_ITEMS = 8
MAX_PREVIEW_ITEMS_PER_SOURCE = 4
FETCH_TIMEOUT_SECONDS = 4
MAX_REDIRECTS = 3

_USER_AGENT = "paperboy/0.2 (+https://github.com/cgallic/paperboy)"
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.+#-]*", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
_STOPWORDS = {
    "a", "about", "all", "an", "and", "are", "as", "at", "be", "by",
    "for", "from", "how", "i", "in", "is", "it", "my", "of", "on",
    "or", "our", "that", "the", "their", "this", "to", "what", "when",
    "where", "which", "who", "why", "with", "you", "your",
}


class PreviewValidationError(ValueError):
    """The preview request itself is invalid."""


class FeedFetchError(RuntimeError):
    """A single source could not be safely fetched or parsed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _tokens(text: str, *, remove_stopwords: bool = True) -> tuple[str, ...]:
    raw = (match.group(0).casefold() for match in _TOKEN_RE.finditer(text))
    if remove_stopwords:
        return tuple(token for token in raw if token not in _STOPWORDS and len(token) > 1)
    return tuple(raw)


def validate_preview_payload(payload: Any) -> tuple[list[str], str, list[str]]:
    """Validate and normalize the three-field preview request."""
    if not isinstance(payload, dict):
        raise PreviewValidationError("request body must be a JSON object")

    unknown = set(payload) - {"sources", "focus", "ignore"}
    if unknown:
        raise PreviewValidationError("request contains unsupported fields")

    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise PreviewValidationError("sources must be a non-empty list")
    if len(raw_sources) > MAX_SOURCES:
        raise PreviewValidationError(f"sources may contain at most {MAX_SOURCES} URLs")

    sources: list[str] = []
    seen_sources: set[str] = set()
    for value in raw_sources:
        if not isinstance(value, str) or not value.strip():
            raise PreviewValidationError("each source must be a non-empty URL string")
        source = value.strip()
        if len(source) > MAX_SOURCE_URL_CHARS:
            raise PreviewValidationError("a source URL is too long")
        if source not in seen_sources:
            seen_sources.add(source)
            sources.append(source)

    focus_value = payload.get("focus")
    if not isinstance(focus_value, str) or not focus_value.strip():
        raise PreviewValidationError("focus must be a non-empty string")
    focus = _WHITESPACE_RE.sub(" ", focus_value.strip())
    if len(focus) > MAX_FOCUS_CHARS:
        raise PreviewValidationError(f"focus may contain at most {MAX_FOCUS_CHARS} characters")
    if not _tokens(focus):
        raise PreviewValidationError("focus must include at least one meaningful term")

    raw_ignore = payload.get("ignore", [])
    if raw_ignore is None:
        raw_ignore = []
    if not isinstance(raw_ignore, list):
        raise PreviewValidationError("ignore must be a list of strings")
    if len(raw_ignore) > MAX_IGNORE_TERMS:
        raise PreviewValidationError(f"ignore may contain at most {MAX_IGNORE_TERMS} terms")
    ignore: list[str] = []
    for value in raw_ignore:
        if not isinstance(value, str) or not value.strip():
            raise PreviewValidationError("each ignore term must be a non-empty string")
        term = _WHITESPACE_RE.sub(" ", value.strip())
        if len(term) > MAX_IGNORE_TERM_CHARS:
            raise PreviewValidationError("an ignore term is too long")
        ignore.append(term)
    return sources, focus, ignore


def _resolved_public_addresses(hostname: str, port: int) -> tuple[str, ...]:
    try:
        answers = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FeedFetchError("dns_failed") from exc
    addresses = tuple(sorted({str(answer[4][0]).split("%", 1)[0] for answer in answers}))
    if not addresses:
        raise FeedFetchError("dns_failed")
    try:
        parsed = tuple(ipaddress.ip_address(address) for address in addresses)
    except ValueError as exc:
        raise FeedFetchError("dns_failed") from exc
    if any(not address.is_global for address in parsed):
        raise FeedFetchError("blocked_url")
    return addresses


def validate_public_feed_url(url: str) -> str:
    """Return a normalized fetch URL or reject unsafe/non-public destinations."""
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise FeedFetchError("invalid_url") from exc
    if parsed.scheme.casefold() not in {"http", "https"}:
        raise FeedFetchError("invalid_url")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise FeedFetchError("invalid_url")
    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise FeedFetchError("blocked_url")
    expected_port = 443 if parsed.scheme.casefold() == "https" else 80
    if port is not None and port != expected_port:
        raise FeedFetchError("blocked_url")
    _resolved_public_addresses(hostname, port or expected_port)
    return urllib.parse.urlunsplit((parsed.scheme.casefold(), parsed.netloc, parsed.path or "/", parsed.query, ""))


def _read_limited(response: Any) -> bytes:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > MAX_FEED_BYTES:
                raise FeedFetchError("body_too_large")
        except ValueError:
            pass
    body = bytes(response.read(MAX_FEED_BYTES + 1))
    if len(body) > MAX_FEED_BYTES:
        raise FeedFetchError("body_too_large")
    return body


def _fetch_public_feed(url: str) -> tuple[bytes, str]:
    """Fetch one public feed, validating DNS, the peer, and every redirect."""
    current = url
    for redirect_count in range(MAX_REDIRECTS + 1):
        current = validate_public_feed_url(current)
        parsed = urllib.parse.urlsplit(current)
        hostname = parsed.hostname
        if hostname is None:
            raise FeedFetchError("invalid_url")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        connection: http.client.HTTPConnection
        if parsed.scheme == "https":
            connection = http.client.HTTPSConnection(hostname, port, timeout=FETCH_TIMEOUT_SECONDS)
        else:
            connection = http.client.HTTPConnection(hostname, port, timeout=FETCH_TIMEOUT_SECONDS)
        try:
            connection.connect()
            if connection.sock is None:
                raise FeedFetchError("fetch_failed")
            peer = str(connection.sock.getpeername()[0]).split("%", 1)[0]
            try:
                peer_address = ipaddress.ip_address(peer)
            except ValueError as exc:
                raise FeedFetchError("fetch_failed") from exc
            if not peer_address.is_global:
                raise FeedFetchError("blocked_url")
            target = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
            connection.request(
                "GET",
                target,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml;q=0.9",
                },
            )
            response = connection.getresponse()
            if 200 <= response.status < 300:
                return _read_limited(response), current
            if response.status in {301, 302, 303, 307, 308} and redirect_count < MAX_REDIRECTS:
                location = response.headers.get("Location")
                if not location:
                    raise FeedFetchError("redirect_failed")
                current = urllib.parse.urljoin(current, location)
                continue
            if response.status in {301, 302, 303, 307, 308}:
                raise FeedFetchError("too_many_redirects")
            if 400 <= response.status <= 599:
                raise FeedFetchError(f"http_{response.status}")
            raise FeedFetchError("fetch_failed")
        except FeedFetchError:
            raise
        except TimeoutError as exc:
            raise FeedFetchError("timeout") from exc
        except (http.client.HTTPException, OSError) as exc:
            raise FeedFetchError("fetch_failed") from exc
        finally:
            connection.close()
    raise FeedFetchError("too_many_redirects")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _direct_child_text(element: ElementTree.Element, names: tuple[str, ...]) -> str:
    for child in element:
        if _local_name(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def _clean_text(raw: str, limit: int) -> str:
    if not raw:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(html.unescape(raw))
        parser.close()
        text = " ".join(parser.parts)
    except Exception:
        text = raw
    return _WHITESPACE_RE.sub(" ", text).strip()[:limit]


def _item_link(element: ElementTree.Element, feed_url: str) -> str | None:
    fallback = ""
    for child in element:
        if _local_name(child.tag) != "link":
            continue
        href = (child.get("href") or "").strip()
        rel = (child.get("rel") or "alternate").casefold()
        candidate = href or (child.text or "").strip()
        if not candidate:
            continue
        if rel in {"alternate", ""}:
            fallback = candidate
            break
        if not fallback:
            fallback = candidate
    if not fallback:
        return None
    absolute = urllib.parse.urljoin(feed_url, fallback)
    try:
        parsed = urllib.parse.urlsplit(absolute)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return None
    if port is not None and port != (443 if parsed.scheme.casefold() == "https" else 80):
        return None
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        return None
    return urllib.parse.urlunsplit((parsed.scheme.casefold(), parsed.netloc, parsed.path or "/", parsed.query, ""))


def _parse_feed(body: bytes, feed_url: str) -> tuple[str, list[dict[str, str]]]:
    """Parse a conservative RSS/Atom subset into source-linked items."""
    if b"<!DOCTYPE" in body[:65536].upper() or b"<!ENTITY" in body[:65536].upper():
        raise FeedFetchError("invalid_feed")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise FeedFetchError("invalid_feed") from exc

    container = root
    for child in root:
        if _local_name(child.tag) == "channel":
            container = child
            break
    source = _clean_text(_direct_child_text(container, ("title",)), 120)
    if not source:
        source = urllib.parse.urlsplit(feed_url).hostname or "Feed"

    parsed_items: list[dict[str, str]] = []
    for element in root.iter():
        if _local_name(element.tag) not in {"item", "entry"}:
            continue
        title = _clean_text(_direct_child_text(element, ("title",)), 240)
        link = _item_link(element, feed_url)
        summary = _clean_text(
            _direct_child_text(element, ("description", "summary", "content")),
            600,
        )
        if title and link:
            parsed_items.append({"title": title, "url": link, "summary": summary})
        if len(parsed_items) >= MAX_PARSED_ITEMS_PER_SOURCE:
            break
    if not parsed_items:
        raise FeedFetchError("empty_feed")
    return source, parsed_items


def _fetch_and_parse_source(url: str) -> tuple[str, list[dict[str, str]]]:
    body, final_url = _fetch_public_feed(url)
    return _parse_feed(body, final_url)


def _canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    hostname = (parsed.hostname or "").casefold()
    port = parsed.port
    if port and port != (443 if parsed.scheme.casefold() == "https" else 80):
        hostname = f"{hostname}:{port}"
    query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in _TRACKING_QUERY_KEYS
    ]
    return urllib.parse.urlunsplit(
        (parsed.scheme.casefold(), hostname, parsed.path.rstrip("/") or "/", urllib.parse.urlencode(sorted(query)), "")
    )


def _contains_sequence(tokens: tuple[str, ...], sequence: tuple[str, ...]) -> bool:
    if not sequence or len(sequence) > len(tokens):
        return False
    width = len(sequence)
    return any(tokens[index:index + width] == sequence for index in range(len(tokens) - width + 1))


def _score_item(
    item: dict[str, str],
    focus_terms: tuple[str, ...],
    ignore_sequences: tuple[tuple[str, ...], ...],
) -> tuple[int, tuple[str, ...]] | None:
    title_tokens = _tokens(item["title"], remove_stopwords=False)
    summary_tokens = _tokens(item.get("summary", ""), remove_stopwords=False)
    combined_tokens = title_tokens + summary_tokens
    if any(_contains_sequence(combined_tokens, sequence) for sequence in ignore_sequences):
        return None

    title_set = set(title_tokens)
    summary_set = set(summary_tokens)
    ordered_focus = tuple(dict.fromkeys(focus_terms))
    title_hits = tuple(term for term in ordered_focus if term in title_set)
    summary_hits = tuple(term for term in ordered_focus if term in summary_set and term not in title_set)
    matches = title_hits + summary_hits
    if not matches:
        return None

    coverage = round(20 * len(set(matches)) / len(ordered_focus))
    score = 15 * len(title_hits) + 6 * len(summary_hits) + coverage
    focus_bigrams = tuple(zip(ordered_focus, ordered_focus[1:], strict=False))
    score += 8 * sum(1 for bigram in focus_bigrams if _contains_sequence(title_tokens, bigram))
    return min(100, score), matches[:4]


def build_firehose_preview(
    sources: list[str],
    focus: str,
    ignore: list[str],
    *,
    fetcher: Callable[[str], tuple[str, list[dict[str, str]]]] | None = None,
) -> dict[str, Any]:
    """Fetch, rank, and dedupe a short preview without persistence."""
    source_fetcher = fetcher or _fetch_and_parse_source
    source_results: list[dict[str, str]] = []
    candidates: list[dict[str, Any]] = []
    scanned = 0
    focus_terms = _tokens(focus)
    ignore_sequences = tuple(sequence for sequence in (_tokens(term, remove_stopwords=False) for term in ignore) if sequence)

    for source_url in sources:
        try:
            source_label, raw_items = source_fetcher(source_url)
        except FeedFetchError as exc:
            source_results.append({"url": source_url, "status": "error", "error": exc.code})
            continue
        except Exception:
            source_results.append({"url": source_url, "status": "error", "error": "fetch_failed"})
            continue

        source_results.append({"url": source_url, "status": "ok"})
        scanned += len(raw_items)
        for raw_item in raw_items:
            scored = _score_item(raw_item, focus_terms, ignore_sequences)
            if scored is None:
                continue
            score, matches = scored
            candidate: dict[str, Any] = {
                "title": raw_item["title"],
                "url": raw_item["url"],
                "source": source_label,
                "source_url": source_url,
                "score": score,
                "why": f"Matches focus: {', '.join(matches)}",
                "summary": raw_item.get("summary", "")[:240],
                "canonical_url": _canonical_url(raw_item["url"]),
                "canonical_title": " ".join(_tokens(raw_item["title"], remove_stopwords=False)),
            }
            candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            -int(item["score"]),
            str(item["title"]).casefold(),
            str(item["canonical_url"]),
            str(item["source_url"]),
        )
    )
    selected: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    source_counts: Counter[str] = Counter()
    for candidate in candidates:
        canonical_url = str(candidate.pop("canonical_url"))
        canonical_title = str(candidate.pop("canonical_title"))
        source_url = str(candidate.pop("source_url"))
        if canonical_url in seen_urls or canonical_title in seen_titles:
            continue
        if source_counts[source_url] >= MAX_PREVIEW_ITEMS_PER_SOURCE:
            continue
        if not candidate.get("summary"):
            candidate.pop("summary", None)
        seen_urls.add(canonical_url)
        seen_titles.add(canonical_title)
        source_counts[source_url] += 1
        selected.append(candidate)
        if len(selected) >= MAX_PREVIEW_ITEMS:
            break

    return {
        "ok": True,
        "items": selected,
        "sources": source_results,
        "scanned": scanned,
    }
