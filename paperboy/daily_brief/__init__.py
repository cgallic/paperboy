"""Deterministic, local-only Daily Intelligence Brief sample domain."""

from paperboy.daily_brief.brief import build_daily_brief, render_html, render_text
from paperboy.daily_brief.models import (
    BriefEdition,
    BriefFixture,
    BriefItem,
    ExternalSignal,
    ImpactVerdict,
    RepoProfile,
    RunConfig,
)

__all__ = [
    "BriefEdition",
    "BriefFixture",
    "BriefItem",
    "ExternalSignal",
    "ImpactVerdict",
    "RepoProfile",
    "RunConfig",
    "build_daily_brief",
    "render_html",
    "render_text",
]
