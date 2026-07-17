"""Selection and email rendering for the deterministic Daily Intelligence Brief."""
from __future__ import annotations

import hashlib
import html
import json
from collections import Counter
from dataclasses import replace
from typing import Iterable

from paperboy.daily_brief.models import (
    BriefEdition,
    BriefItem,
    ExternalSignal,
    ImpactVerdict,
    RepoProfile,
    RunConfig,
)


def _unique_index(items: Iterable[object], attr: str, label: str) -> dict[str, object]:
    out: dict[str, object] = {}
    for item in items:
        key = getattr(item, attr)
        if key in out:
            raise ValueError(f"duplicate {label}: {key}")
        out[key] = item
    return out


def _item_id(policy_version: str, signal: ExternalSignal, repo_id: str | None) -> str:
    raw = f"{policy_version}:{signal.source_kind}:{signal.id}:{repo_id or '-'}"
    return "brief_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def build_daily_brief(
    config: RunConfig,
    repos: Iterable[RepoProfile],
    signals: Iterable[ExternalSignal],
    verdicts: Iterable[ImpactVerdict],
) -> BriefEdition:
    """Build one edition without I/O, time, environment, DB, or network access."""
    repos = tuple(repos)
    signals = tuple(signals)
    verdicts = tuple(verdicts)
    if len(repos) > config.max_repos:
        raise ValueError(
            f"daily brief accepts at most {config.max_repos} public repo profiles"
        )

    repo_by_id = _unique_index(repos, "id", "repo id")
    signal_by_id = _unique_index(signals, "id", "signal id")

    candidates: list[BriefItem] = []
    seen_impacts: set[tuple[str, str | None]] = set()
    for verdict in verdicts:
        signal_obj = signal_by_id.get(verdict.signal_id)
        if signal_obj is None:
            raise ValueError(f"verdict references unknown signal: {verdict.signal_id}")
        signal = signal_obj
        assert isinstance(signal, ExternalSignal)
        repo: RepoProfile | None = None
        if verdict.repo_id is not None:
            repo_obj = repo_by_id.get(verdict.repo_id)
            if repo_obj is None:
                raise ValueError(f"verdict references unknown repo: {verdict.repo_id}")
            repo = repo_obj  # type: ignore[assignment]
        dedup_key = (verdict.signal_id, verdict.repo_id)
        if dedup_key in seen_impacts:
            continue
        seen_impacts.add(dedup_key)
        if not (config.period_start <= signal.occurred_at < config.period_end):
            continue
        if verdict.relevance < config.min_relevance:
            continue
        candidates.append(BriefItem(
            id=_item_id(config.policy_version, signal, verdict.repo_id),
            rank=0,
            section=signal.section,
            source_kind=signal.source_kind,
            source_label=signal.source_label,
            signal_id=signal.id,
            occurred_at=signal.occurred_at,
            headline=signal.headline,
            what_changed=signal.what_changed,
            score=verdict.relevance,
            why_it_matters=verdict.why_it_matters,
            next_step=verdict.next_step,
            action_kind=verdict.action_kind,
            evidence_urls=signal.evidence_urls,
            repo_id=repo.id if repo else None,
            repo_full_name=repo.full_name if repo else None,
        ))

    candidates.sort(key=lambda item: (
        -item.score,
        -item.occurred_at.timestamp(),
        item.repo_full_name or "",
        item.source_kind,
        item.signal_id,
    ))

    source_counts: Counter[str] = Counter()
    selected: list[BriefItem] = []
    for item in candidates:
        if source_counts[item.source_kind] >= config.max_per_source:
            continue
        selected.append(item)
        source_counts[item.source_kind] += 1
        if len(selected) >= config.max_items:
            break

    selected = [replace(item, rank=index) for index, item in enumerate(selected, 1)]
    hash_payload = [
        {"id": item.id, "score": item.score, "rank": item.rank}
        for item in selected
    ]
    candidate_hash = hashlib.sha256(
        json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if not selected:
        return BriefEdition(
            config=config,
            status="quiet",
            skip_reason="no_threshold_items",
            candidate_hash=candidate_hash,
            items=(),
        )
    return BriefEdition(
        config=config,
        status="ready",
        skip_reason=None,
        candidate_hash=candidate_hash,
        items=tuple(selected),
    )


def _long_date(edition: BriefEdition) -> str:
    value = edition.config.edition_date
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def subject_for(edition: BriefEdition) -> str | None:
    if edition.is_quiet:
        return "Paperboy · nothing material changed this morning"
    return f"Paperboy · {len(edition.items)} things worth knowing this morning"


def preheader_for(edition: BriefEdition) -> str | None:
    if edition.is_quiet:
        return "Your sources ran; nothing cleared the relevance bar."
    source_count = len({item.source_kind for item in edition.items})
    return f"Your ranked morning edition across {source_count} source types."


def _section_groups(edition: BriefEdition) -> list[tuple[str, list[BriefItem]]]:
    grouped: dict[str, list[BriefItem]] = {}
    for item in edition.items:
        grouped.setdefault(item.section, []).append(item)
    order = {section: index for index, section in enumerate(edition.config.section_order)}
    return sorted(grouped.items(), key=lambda pair: (order.get(pair[0], len(order)), pair[0].lower()))


def render_text(edition: BriefEdition) -> str | None:
    """Return an email-ready plain-text artifact, including quiet editions."""
    subject = subject_for(edition)
    preheader = preheader_for(edition)
    if subject is None or preheader is None:
        return None
    label = "SAMPLE · " if edition.config.sample else ""
    lines = [
        f"Subject: {subject}",
        f"Preheader: {preheader}",
        "",
        f"{label}PAPERBOY · DAILY INTELLIGENCE BRIEF",
        _long_date(edition),
    ]
    if edition.is_quiet:
        lines.extend([
            "",
            "Nothing material changed",
            "Your sources ran. Nothing cleared your relevance bar today.",
        ])
    else:
        lines.append(
            f"{len(edition.items)} items across {len({i.source_kind for i in edition.items})} source types"
        )
    for section, items in _section_groups(edition):
        lines.extend(["", section.upper(), "=" * len(section)])
        for item in items:
            repo = f" · {item.repo_full_name}" if item.repo_full_name else ""
            lines.extend([
                "",
                f"{item.source_label.upper()} · {item.score}/10{repo}",
                item.headline,
                "",
                "What changed",
                item.what_changed,
                "",
                "Why it matters",
                item.why_it_matters,
                "",
                "Next move",
                item.next_step,
                "",
                f"View source evidence: {item.evidence_urls[0]}",
            ])
    lines.extend([
        "",
        "---",
        f"Scheduled for {edition.config.schedule_label}.",
        "This local sample was rendered from sanitized fixtures. No email was sent.",
    ])
    return "\n".join(lines) + "\n"


def render_html(edition: BriefEdition) -> str | None:
    """Return a self-contained, escaped email HTML artifact, including quiet editions."""
    subject = subject_for(edition)
    preheader = preheader_for(edition)
    if subject is None or preheader is None:
        return None
    chunks: list[str] = []
    for section, items in _section_groups(edition):
        item_html: list[str] = []
        for item in items:
            repo = f" · {html.escape(item.repo_full_name)}" if item.repo_full_name else ""
            evidence = html.escape(item.evidence_urls[0], quote=True)
            item_html.append(f"""
              <article style="border-top:1px solid #D4CCBD;padding:22px 0;">
                <p style="margin:0 0 8px;font:600 12px/18px monospace;color:#555C63;text-transform:uppercase;">{html.escape(item.source_label)} · {item.score}/10{repo}</p>
                <h2 style="margin:0 0 16px;font:600 24px/30px Georgia,serif;color:#15171A;">{html.escape(item.headline)}</h2>
                <p style="margin:0 0 4px;font:600 13px/20px Arial,sans-serif;color:#15171A;">What changed</p>
                <p style="margin:0 0 14px;font:400 16px/24px Arial,sans-serif;color:#15171A;">{html.escape(item.what_changed)}</p>
                <p style="margin:0 0 4px;font:600 13px/20px Arial,sans-serif;color:#15171A;">Why it matters</p>
                <p style="margin:0 0 14px;font:400 16px/24px Arial,sans-serif;color:#15171A;">{html.escape(item.why_it_matters)}</p>
                <p style="margin:0 0 4px;font:600 13px/20px Arial,sans-serif;color:#15171A;">Next move</p>
                <p style="margin:0 0 14px;border-left:3px solid #2864DC;padding-left:12px;font:500 16px/24px Arial,sans-serif;color:#15171A;">{html.escape(item.next_step)}</p>
                <a href="{evidence}" style="color:#2864DC;font:600 14px/20px Arial,sans-serif;">View source evidence</a>
              </article>""")
        chunks.append(f"""
            <section>
              <h1 style="margin:26px 0 8px;font:600 13px/20px monospace;color:#17489F;text-transform:uppercase;letter-spacing:.08em;">{html.escape(section)}</h1>
              {''.join(item_html)}
            </section>""")
    sample = "SAMPLE · " if edition.config.sample else ""
    if edition.is_quiet:
        summary = """
    <section style="border-top:1px solid #D4CCBD;margin-top:24px;padding:24px 0;">
      <h2 style="margin:0 0 10px;font:600 24px/30px Georgia,serif;color:#15171A;">Nothing material changed</h2>
      <p style="margin:0;font:400 16px/24px Arial,sans-serif;color:#15171A;">Your sources ran. Nothing cleared your relevance bar today.</p>
    </section>"""
    else:
        summary = f'<p style="margin:8px 0 24px;font:400 15px/22px Arial,sans-serif;color:#555C63;">{len(edition.items)} items across {len({i.source_kind for i in edition.items})} source types</p>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{html.escape(subject)}</title></head>
<body style="margin:0;background:#F3EEE3;color:#15171A;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{html.escape(preheader)}</div>
  <main style="box-sizing:border-box;max-width:640px;margin:0 auto;padding:32px 24px;background:#FBF8F1;">
    <p style="margin:0 0 8px;font:600 12px/18px monospace;color:#2864DC;letter-spacing:.08em;">{sample}PAPERBOY · DAILY INTELLIGENCE BRIEF</p>
    <h1 style="margin:0;font:600 34px/40px Georgia,serif;color:#15171A;">{html.escape(_long_date(edition))}</h1>
    {summary}
    {''.join(chunks)}
    <footer style="border-top:1px solid #D4CCBD;padding-top:18px;font:400 13px/20px Arial,sans-serif;color:#555C63;">
      <p>Scheduled for {html.escape(edition.config.schedule_label)}.</p>
      <p>This local sample was rendered from sanitized fixtures. No email was sent.</p>
    </footer>
  </main>
</body></html>"""
