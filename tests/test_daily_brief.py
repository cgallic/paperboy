from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from paperboy.daily_brief.brief import build_daily_brief, render_html, render_text
from paperboy.daily_brief.cli import load_fixture, run
from paperboy.daily_brief.models import BriefFixture, ImpactVerdict

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "daily-brief.sample.json"
QUIET = ROOT / "examples" / "daily-brief.quiet.json"


class DailyBriefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = load_fixture(SAMPLE)

    def build(self, fixture: BriefFixture | None = None):
        fixture = fixture or self.fixture
        return build_daily_brief(fixture.config, fixture.repos, fixture.signals, fixture.verdicts)

    def test_golden_sample_is_ranked_capped_and_email_ready(self) -> None:
        edition = self.build()
        self.assertEqual("ready", edition.status)
        self.assertEqual(6, len(edition.items))
        self.assertLessEqual(len(edition.items), 12)
        self.assertEqual("news-tool-streaming", edition.items[0].signal_id)
        self.assertEqual("example-labs/agent-core", edition.items[0].repo_full_name)
        self.assertEqual(tuple(range(1, 7)), tuple(item.rank for item in edition.items))
        self.assertTrue(all(item.evidence_urls for item in edition.items))
        text = render_text(edition)
        html = render_html(edition)
        self.assertIsNotNone(text)
        self.assertIsNotNone(html)
        assert text is not None and html is not None
        self.assertIn("Subject: Paperboy · 6 things worth knowing this morning", text)
        self.assertIn("FROM YOUR NEWSLETTERS", text)
        self.assertIn("Why it matters", text)
        self.assertIn("Next move", text)
        self.assertIn("View source evidence", text)
        self.assertIn("max-width:640px", html)
        self.assertNotIn("Approve", html)

    def test_input_order_does_not_change_output(self) -> None:
        first = self.build()
        shuffled = BriefFixture(
            config=self.fixture.config,
            repos=tuple(reversed(self.fixture.repos)),
            signals=tuple(reversed(self.fixture.signals)),
            verdicts=tuple(reversed(self.fixture.verdicts)),
        )
        second = self.build(shuffled)
        self.assertEqual(first.candidate_hash, second.candidate_hash)
        self.assertEqual(render_text(first), render_text(second))
        self.assertEqual(render_html(first), render_html(second))

    def test_threshold_period_dedup_and_source_diversity(self) -> None:
        base_signal = self.fixture.signals[0]
        signals = []
        verdicts = []
        for index in range(16):
            source = "news" if index < 10 else f"source-{index}"
            signal = replace(
                base_signal,
                id=f"signal-{index}",
                source_kind=source,
                source_label=source,
                section="News",
                headline=f"Signal {index}",
            )
            signals.append(signal)
            verdicts.append(ImpactVerdict(
                signal_id=signal.id,
                relevance=10 - (index % 3),
                why_it_matters="It may change a current decision.",
                next_step="Inspect one bounded comparison.",
                action_kind="act",
            ))
        verdicts.append(verdicts[0])
        config = replace(self.fixture.config, max_items=12, max_per_source=3)
        edition = build_daily_brief(config, (), signals, verdicts)
        self.assertEqual(9, len(edition.items))
        self.assertLessEqual(sum(item.source_kind == "news" for item in edition.items), 3)
        self.assertEqual(len({item.id for item in edition.items}), len(edition.items))

        boundary_start = replace(base_signal, id="at-start", occurred_at=config.period_start)
        boundary_end = replace(base_signal, id="at-end", occurred_at=config.period_end)
        boundary = build_daily_brief(config, (), (boundary_start, boundary_end), (
            ImpactVerdict("at-start", 7, "Relevant now.", "Inspect it.", "act"),
            ImpactVerdict("at-end", 10, "Too late.", "Inspect it.", "act"),
        ))
        self.assertEqual(("at-start",), tuple(item.signal_id for item in boundary.items))

    def test_quiet_day_preserves_ritual_without_padding(self) -> None:
        fixture = load_fixture(QUIET)
        edition = self.build(fixture)
        self.assertEqual("quiet", edition.status)
        self.assertEqual("no_threshold_items", edition.skip_reason)
        self.assertEqual((), edition.items)
        text = render_text(edition)
        html = render_html(edition)
        self.assertIsNotNone(text)
        self.assertIsNotNone(html)
        assert text is not None and html is not None
        self.assertIn("nothing material changed this morning", text)
        self.assertIn("Nothing material changed", html)
        self.assertNotIn("View source evidence", text)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "quiet-edition"
            result = run(QUIET, out)
            self.assertEqual("quiet", result["status"])
            self.assertEqual(2, len(result["written"]))
            self.assertTrue(out.exists())

    def test_cli_writes_only_local_text_and_html(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "artifacts"
            result = run(SAMPLE, out)
            self.assertEqual("ready", result["status"])
            self.assertEqual(2, len(result["written"]))
            self.assertEqual(
                {"paperboy-daily-brief.txt", "paperboy-daily-brief.html"},
                {path.name for path in out.iterdir()},
            )

    def test_renderer_escapes_untrusted_source_text(self) -> None:
        hostile = replace(
            self.fixture.signals[0],
            headline="<script>alert('x')</script>",
            what_changed="A <b>claim</b> & more",
        )
        fixture = replace(
            self.fixture,
            signals=(hostile,) + self.fixture.signals[1:],
        )
        rendered = render_html(self.build(fixture))
        assert rendered is not None
        self.assertNotIn("<script>alert", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("A &lt;b&gt;claim&lt;/b&gt; &amp; more", rendered)

    def test_validation_rejects_private_or_too_many_repos_and_unknown_refs(self) -> None:
        raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
        raw["repos"][0]["visibility"] = "private"
        with self.assertRaisesRegex(ValueError, "only public"):
            BriefFixture.from_dict(raw)

        repos = tuple(
            replace(
                self.fixture.repos[0],
                id=f"repo-{index}",
                full_name=f"example-labs/repo-{index}",
                url=f"https://github.com/example-labs/repo-{index}",
            )
            for index in range(6)
        )
        with self.assertRaisesRegex(ValueError, "at most 5"):
            build_daily_brief(self.fixture.config, repos, (), ())
        expanded_config = replace(self.fixture.config, max_repos=6)
        self.assertEqual((), build_daily_brief(expanded_config, repos, (), ()).items)

        unknown = ImpactVerdict(
            signal_id=self.fixture.signals[0].id,
            repo_id="not-selected",
            relevance=9,
            why_it_matters="Would leak if accepted.",
            next_step="Inspect nothing.",
            action_kind="act",
        )
        with self.assertRaisesRegex(ValueError, "unknown repo"):
            build_daily_brief(self.fixture.config, self.fixture.repos, self.fixture.signals, (unknown,))

    def test_watch_requires_explicit_do_nothing(self) -> None:
        with self.assertRaisesRegex(ValueError, "do nothing"):
            ImpactVerdict(
                signal_id="signal",
                relevance=7,
                why_it_matters="Maybe relevant.",
                next_step="Keep watching.",
                action_kind="watch",
            )


if __name__ == "__main__":
    unittest.main()
