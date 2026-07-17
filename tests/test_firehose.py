from __future__ import annotations

import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from paperboy.api.main import app
from paperboy.firehose import (
    MAX_PREVIEW_ITEMS,
    MAX_PREVIEW_ITEMS_PER_SOURCE,
    MAX_REQUEST_BYTES,
    MAX_SOURCES,
    FeedFetchError,
    PreviewValidationError,
    _fetch_public_feed,
    _parse_feed,
    build_firehose_preview,
    validate_preview_payload,
    validate_public_feed_url,
)

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>Builder News</title>
  <item>
    <title>AI agents make retrieval pipelines easier to inspect</title>
    <link>https://example.com/agents?utm_source=test</link>
    <description><![CDATA[<p>A practical agent orchestration and retrieval guide.</p>]]></description>
  </item>
  <item>
    <title>Unrelated sports result</title>
    <link>https://example.com/sports</link>
    <description>No technical relevance.</description>
  </item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>YC Engineering</title>
  <entry>
    <title>Retrieval systems for startup agents</title>
    <link rel="self" href="https://feeds.example.com/entry/1" />
    <link rel="alternate" href="https://example.com/retrieval-agents" />
    <summary type="html">&lt;b&gt;Agent retrieval&lt;/b&gt; without the noise.</summary>
  </entry>
</feed>"""


class FirehoseValidationTests(unittest.TestCase):
    def test_payload_requires_exact_bounded_fields(self) -> None:
        sources, focus, ignore = validate_preview_payload(
            {
                "sources": ["https://example.com/feed", "https://example.com/feed"],
                "focus": "  AI agents and retrieval  ",
                "ignore": ["funding gossip"],
            }
        )
        self.assertEqual(sources, ["https://example.com/feed"])
        self.assertEqual(focus, "AI agents and retrieval")
        self.assertEqual(ignore, ["funding gossip"])

        with self.assertRaises(PreviewValidationError):
            validate_preview_payload({"sources": [], "focus": "agents"})
        with self.assertRaises(PreviewValidationError):
            validate_preview_payload(
                {
                    "sources": [f"https://example.com/{index}" for index in range(MAX_SOURCES + 1)],
                    "focus": "agents",
                }
            )
        with self.assertRaises(PreviewValidationError):
            validate_preview_payload({"sources": ["https://example.com/feed"], "focus": "agents", "extra": True})

    def test_public_url_validation_blocks_private_resolution_and_ports(self) -> None:
        private_answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
        with (
            patch("paperboy.firehose.socket.getaddrinfo", return_value=private_answer),
            self.assertRaises(FeedFetchError) as caught,
        ):
            validate_public_feed_url("http://example.com/feed")
        self.assertEqual(caught.exception.code, "blocked_url")

        public_answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with patch("paperboy.firehose.socket.getaddrinfo", return_value=public_answer):
            self.assertEqual(
                validate_public_feed_url("https://example.com/feed#fragment"),
                "https://example.com/feed",
            )
            with self.assertRaises(FeedFetchError) as port_error:
                validate_public_feed_url("https://example.com:8443/feed")
        self.assertEqual(port_error.exception.code, "blocked_url")

    def test_connected_peer_is_rechecked_before_request(self) -> None:
        class FakeSocket:
            def getpeername(self) -> tuple[str, int]:
                return ("127.0.0.1", 443)

        class FakeConnection:
            sock = FakeSocket()

            def connect(self) -> None:
                return None

            def request(self, *_args: object, **_kwargs: object) -> None:
                self.fail_if_called()

            def fail_if_called(self) -> None:
                raise AssertionError("request must not be sent to a private peer")

            def close(self) -> None:
                return None

        public_answer = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with (
            patch("paperboy.firehose.socket.getaddrinfo", return_value=public_answer),
            patch("paperboy.firehose.http.client.HTTPSConnection", return_value=FakeConnection()),
            self.assertRaises(FeedFetchError) as caught,
        ):
            _fetch_public_feed("https://example.com/feed")
        self.assertEqual(caught.exception.code, "blocked_url")


class FirehoseParsingTests(unittest.TestCase):
    def test_parses_basic_rss_and_cleans_summary(self) -> None:
        source, items = _parse_feed(RSS, "https://feed.example.com/rss")
        self.assertEqual(source, "Builder News")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "AI agents make retrieval pipelines easier to inspect")
        self.assertEqual(items[0]["summary"], "A practical agent orchestration and retrieval guide.")

    def test_parses_atom_and_prefers_alternate_link(self) -> None:
        source, items = _parse_feed(ATOM, "https://feed.example.com/atom")
        self.assertEqual(source, "YC Engineering")
        self.assertEqual(items[0]["url"], "https://example.com/retrieval-agents")
        self.assertEqual(items[0]["summary"], "Agent retrieval without the noise.")

    def test_invalid_or_empty_xml_is_a_source_error(self) -> None:
        with self.assertRaises(FeedFetchError) as malformed:
            _parse_feed(b"not xml", "https://example.com/feed")
        self.assertEqual(malformed.exception.code, "invalid_feed")


class FirehoseRankingTests(unittest.TestCase):
    def test_ranks_filters_and_dedupes_deterministically(self) -> None:
        def fetcher(url: str) -> tuple[str, list[dict[str, str]]]:
            if url.endswith("one"):
                return (
                    "Source One",
                    [
                        {
                            "title": "AI agents improve retrieval orchestration",
                            "url": "https://example.com/story?utm_source=one",
                            "summary": "A retrieval pipeline for production agents.",
                        },
                        {
                            "title": "AI funding gossip roundup",
                            "url": "https://example.com/gossip",
                            "summary": "Agent startup funding gossip.",
                        },
                        {
                            "title": "A cooking story",
                            "url": "https://example.com/cooking",
                            "summary": "Nothing technical here.",
                        },
                    ],
                )
            return (
                "Source Two",
                [
                    {
                        "title": "AI agents improve retrieval orchestration",
                        "url": "https://example.com/story?utm_campaign=two",
                        "summary": "The same syndicated story.",
                    },
                    {
                        "title": "Retrieval evaluation for AI systems",
                        "url": "https://example.org/evals",
                        "summary": "A deterministic benchmark.",
                    },
                ],
            )

        first = build_firehose_preview(
            ["https://feeds.example.com/one", "https://feeds.example.com/two"],
            "AI agents retrieval orchestration",
            ["funding gossip"],
            fetcher=fetcher,
        )
        second = build_firehose_preview(
            ["https://feeds.example.com/one", "https://feeds.example.com/two"],
            "AI agents retrieval orchestration",
            ["funding gossip"],
            fetcher=fetcher,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["scanned"], 5)
        self.assertEqual(len(first["items"]), 2)
        self.assertGreaterEqual(first["items"][0]["score"], first["items"][1]["score"])
        self.assertNotIn("gossip", " ".join(item["title"].casefold() for item in first["items"]))
        self.assertEqual(first["items"][0]["url"], "https://example.com/story?utm_source=one")
        self.assertEqual(
            set(first["items"][0]),
            {"title", "url", "source", "score", "why", "summary"},
        )

    def test_source_failure_does_not_discard_valid_source(self) -> None:
        def fetcher(url: str) -> tuple[str, list[dict[str, str]]]:
            if url.endswith("bad"):
                raise FeedFetchError("timeout")
            return (
                "Good Feed",
                [{"title": "Agent evaluation", "url": "https://example.com/agent", "summary": "AI testing."}],
            )

        result = build_firehose_preview(
            ["https://feeds.example.com/bad", "https://feeds.example.com/good"],
            "AI agent evaluation",
            [],
            fetcher=fetcher,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["sources"][0], {"url": "https://feeds.example.com/bad", "status": "error", "error": "timeout"})
        self.assertEqual(result["sources"][1], {"url": "https://feeds.example.com/good", "status": "ok"})
        self.assertEqual(len(result["items"]), 1)

    def test_preview_enforces_total_and_per_source_item_caps(self) -> None:
        def fetcher(url: str) -> tuple[str, list[dict[str, str]]]:
            source_id = url.rsplit("/", 1)[-1]
            return (
                f"Source {source_id}",
                [
                    {
                        "title": f"AI agent evaluation {source_id}-{index}",
                        "url": f"https://example.com/{source_id}/{index}",
                        "summary": "Production agent evaluation and retrieval.",
                    }
                    for index in range(12)
                ],
            )

        result = build_firehose_preview(
            ["https://feeds.example.com/one", "https://feeds.example.com/two"],
            "AI agent evaluation retrieval",
            [],
            fetcher=fetcher,
        )
        self.assertEqual(len(result["items"]), MAX_PREVIEW_ITEMS)
        counts: dict[str, int] = {}
        for item in result["items"]:
            counts[item["source"]] = counts.get(item["source"], 0) + 1
        self.assertTrue(all(count <= MAX_PREVIEW_ITEMS_PER_SOURCE for count in counts.values()))

    def test_private_source_is_reported_without_a_network_fetch(self) -> None:
        result = build_firehose_preview(
            ["http://localhost/feed"],
            "AI agents",
            [],
        )
        self.assertEqual(result["scanned"], 0)
        self.assertEqual(
            result["sources"],
            [{"url": "http://localhost/feed", "status": "error", "error": "blocked_url"}],
        )


class FirehoseEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._old_root = os.environ.get("PAPERBOY_ROOT")
        cls._old_db = os.environ.get("PAPERBOY_DB")
        cls._tempdir = tempfile.TemporaryDirectory()
        os.environ["PAPERBOY_ROOT"] = cls._tempdir.name
        os.environ["PAPERBOY_DB"] = str(Path(cls._tempdir.name) / "events.db")
        cls._client_context = TestClient(app)
        cls.client = cls._client_context.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client_context.__exit__(None, None, None)
        if cls._old_root is None:
            os.environ.pop("PAPERBOY_ROOT", None)
        else:
            os.environ["PAPERBOY_ROOT"] = cls._old_root
        if cls._old_db is None:
            os.environ.pop("PAPERBOY_DB", None)
        else:
            os.environ["PAPERBOY_DB"] = cls._old_db
        cls._tempdir.cleanup()

    def test_preview_endpoint_contract_and_partial_failure(self) -> None:
        def fake_source(url: str) -> tuple[str, list[dict[str, str]]]:
            if url.endswith("bad"):
                raise FeedFetchError("http_404")
            return (
                "Hacker News",
                [{"title": "AI agents in production", "url": "https://example.com/agents", "summary": "Agent reliability."}],
            )

        with patch("paperboy.firehose._fetch_and_parse_source", side_effect=fake_source):
            response = self.client.post(
                "/api/firehose/preview",
                json={
                    "sources": ["https://feeds.example.com/good", "https://feeds.example.com/bad"],
                    "focus": "production AI agents",
                    "ignore": ["funding gossip"],
                },
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data), {"ok", "items", "sources", "scanned"})
        self.assertTrue(data["ok"])
        self.assertEqual(data["scanned"], 1)
        self.assertEqual(data["sources"][1]["error"], "http_404")
        self.assertEqual(
            set(data["items"][0]),
            {"title", "url", "source", "score", "why", "summary"},
        )

    def test_preview_endpoint_returns_detail_for_invalid_requests(self) -> None:
        response = self.client.post("/api/firehose/preview", json={"sources": [], "focus": "agents"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("detail", response.json())

        malformed = self.client.post(
            "/api/firehose/preview",
            content=b"{",
            headers={"content-type": "application/json"},
        )
        self.assertEqual(malformed.status_code, 400)
        self.assertIn("detail", malformed.json())

        too_large = self.client.post(
            "/api/firehose/preview",
            content=json.dumps({"sources": ["https://example.com/feed"], "focus": "x" * MAX_REQUEST_BYTES}),
            headers={"content-type": "application/json"},
        )
        self.assertEqual(too_large.status_code, 413)
        self.assertIn("detail", too_large.json())


if __name__ == "__main__":
    unittest.main()
