"""Pydantic-validated configuration for paperboy.

Centralizes all env-var / file config with schema validation,
defaults, and type safety.  Replaces ad-hoc os.environ reads.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PaperboyConfig(BaseSettings):
    """Single source of truth for paperboy configuration."""

    model_config = SettingsConfigDict(
        env_prefix="PAPERBOY_",
        env_file="/etc/paperboy/paperboy.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    app_root: Path = Field(default_factory=Path.cwd)
    root: Path = Field(default_factory=lambda: Path.home() / ".paperboy")
    db: Path | None = None

    # Discord
    discord_webhook: str | None = None
    discord_bot_token: str | None = None
    discord_channel_id: str | None = None

    # Ollama
    ollama_url: str = "http://127.0.0.1:11434"
    fast_model: str = "llama3.2:3b"
    research_model: str = "qwen2.5:7b"

    # Pipeline knobs
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    score_timeout: int = Field(default=240, ge=1, le=3600)
    news_max_per_vertical: int = Field(default=2, ge=1, le=20)
    news_fetch_timeout: int = Field(default=12, ge=1, le=120)
    prompt_digest_limit: int = Field(default=12, ge=1, le=100)
    prompt_digest_lookback_hours: int = Field(default=48, ge=1, le=720)
    prompt_digest_reframe: bool = False
    action_queue_min_relevance: int = Field(default=7, ge=0, le=10)
    action_queue_lookback_hours: int = Field(default=48, ge=1, le=720)
    action_queue_max_prompts: int = Field(default=8, ge=1, le=100)
    papers_min_relevance: int = Field(default=7, ge=0, le=10)
    papers_max_per_run: int = Field(default=5, ge=1, le=100)
    papers_lookback_hours: int = Field(default=24, ge=1, le=720)
    topical_picks_per_run: int = Field(default=2, ge=1, le=20)
    topical_recent_days: int = Field(default=21, ge=1, le=365)
    today_max_per_run: int = Field(default=6, ge=1, le=100)

    # Email (SMTP)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_pass: str | None = None
    smtp_starttls: bool = True
    email_from: str = "paperboy@localhost"
    email_to: str | None = None
    email_reply_to: str | None = None
    bounce_domain: str = "kaibuilds.com"
    resend_webhook_secret: str | None = None

    # Hosted firehose
    public_url: str = "https://newpaperboy.com"
    manage_secret: str | None = None
    tracking_secret: str | None = None
    kaibuilds_capture_url: str | None = None

    # Billing (Stripe-hosted Checkout + customer portal)
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id: str | None = None
    stripe_trial_days: int = Field(default=7, ge=0, le=90)
    stripe_monthly_price_cents: int = Field(default=500, ge=50)
    stripe_currency: str = "usd"

    # API
    dashboard_url: str = ""
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @field_validator("root", mode="before")
    @classmethod
    def _fallback_root(cls, v: Path | str | None) -> Path:
        if v is not None:
            return Path(v)
        p = os.environ.get("PAPERBOY_ROOT") or os.environ.get("BRAIN_ROOT")
        return Path(p) if p else Path.home() / ".paperboy"

    @property
    def db_path(self) -> Path:
        if self.db:
            return self.db
        p = os.environ.get("BRAIN_DB")
        return Path(p) if p else self.root / "events.db"

    @property
    def discord_webhook_url(self) -> str | None:
        return self.discord_webhook or os.environ.get("DISCORD_WEBHOOK_URL")

    @property
    def billing_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_webhook_secret and self.stripe_price_id)


# Singleton — import this everywhere instead of os.environ.get(...)
settings = PaperboyConfig()
