"""
Configuration for Camoufox MCP server.

All settings are read from environment variables (or a .env file).
No secrets or filesystem paths are hardcoded here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Top-level application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="CAMOUFOX_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Browser
    # ------------------------------------------------------------------ #
    headless: bool = Field(default=True, description="Run browser in headless mode")
    humanize: bool = Field(
        default=False, description="Enable Camoufox humanize mode (random delays)"
    )

    # ------------------------------------------------------------------ #
    # Paths  (resolved to absolute at validation time)
    # ------------------------------------------------------------------ #
    profile_dir: Path = Field(
        default=Path("data/profiles"),
        description="Root directory for persistent browser profiles",
    )
    download_dir: Path = Field(
        default=Path("data/downloads"),
        description="Directory for browser downloads",
    )
    screenshot_dir: Path = Field(
        default=Path("data/screenshots"),
        description="Directory for screenshots",
    )

    # ------------------------------------------------------------------ #
    # Session limits
    # ------------------------------------------------------------------ #
    max_sessions: int = Field(
        default=5, ge=1, le=50, description="Maximum concurrent browser sessions"
    )
    session_timeout: int = Field(
        default=3600,
        ge=60,
        description="Idle session timeout in seconds",
    )

    # ------------------------------------------------------------------ #
    # Browser timeouts (milliseconds)
    # ------------------------------------------------------------------ #
    default_timeout: int = Field(
        default=30_000, ge=1_000, description="Default Playwright timeout (ms)"
    )
    navigation_timeout: int = Field(
        default=30_000, ge=1_000, description="Page navigation timeout (ms)"
    )

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Log level"
    )
    log_json: bool = Field(default=False, description="Emit logs as JSON (useful in production)")

    # ------------------------------------------------------------------ #
    # Extraction limits
    # ------------------------------------------------------------------ #
    max_text_length: int = Field(
        default=50_000,
        ge=1_000,
        description="Maximum characters returned by text extraction",
    )
    max_html_length: int = Field(
        default=200_000,
        ge=10_000,
        description="Maximum characters returned by HTML extraction",
    )

    # ------------------------------------------------------------------ #
    # Screenshot
    # ------------------------------------------------------------------ #
    screenshot_quality: int = Field(
        default=80, ge=1, le=100, description="JPEG quality for screenshots"
    )

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator("profile_dir", "download_dir", "screenshot_dir", mode="before")
    @classmethod
    def _resolve_path(cls, v: str | Path) -> Path:
        """Resolve relative paths against CWD at load time."""
        return Path(v).resolve()


def get_settings() -> Settings:
    """Return a Settings instance (reads env / .env file once)."""
    return Settings()
