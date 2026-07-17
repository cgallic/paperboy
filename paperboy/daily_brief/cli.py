"""Local-only CLI for rendering a fixture-driven Daily Intelligence Brief sample."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from paperboy.daily_brief.brief import build_daily_brief, render_html, render_text
from paperboy.daily_brief.models import BriefFixture


def load_fixture(path: Path) -> BriefFixture:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fixture root must be a JSON object")
    return BriefFixture.from_dict(data)


def run(input_path: Path, output_dir: Path) -> dict:
    fixture = load_fixture(input_path)
    edition = build_daily_brief(
        fixture.config,
        fixture.repos,
        fixture.signals,
        fixture.verdicts,
    )
    text = render_text(edition)
    html = render_html(edition)
    assert text is not None and html is not None
    output_dir.mkdir(parents=True, exist_ok=True)
    text_path = output_dir / "paperboy-daily-brief.txt"
    html_path = output_dir / "paperboy-daily-brief.html"
    text_path.write_text(text, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    return {
        "status": edition.status,
        "skip_reason": edition.skip_reason,
        "items": len(edition.items),
        "sources": len({item.source_kind for item in edition.items}),
        "written": [str(text_path), str(html_path)],
        "candidate_hash": edition.candidate_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a local email-ready Paperboy Daily Intelligence Brief from sanitized fixtures"
    )
    parser.add_argument("--input", type=Path, required=True, help="fixture JSON path")
    parser.add_argument("--out-dir", type=Path, required=True, help="local artifact directory")
    args = parser.parse_args()
    try:
        result = run(args.input, args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
