"""
Browser-level Pydantic models.

These describe the browser and context state as seen by MCP clients.
They never expose raw Playwright/Camoufox objects.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BrowserInfo(BaseModel):
    """Snapshot of the browser instance attached to a session."""

    session_id: str
    browser_type: str = "camoufox"
    version: str | None = None
    headless: bool = True


class ContextOptions(BaseModel):
    """Options for creating a new browser context."""

    locale: str = Field(default="en-US", description="Browser locale")
    timezone_id: str = Field(default="UTC", description="Timezone identifier")
    viewport_width: int = Field(default=1280, ge=320, le=3840)
    viewport_height: int = Field(default=720, ge=240, le=2160)
    user_agent: str | None = Field(
        default=None,
        description="Override user agent string (leave None to use Camoufox default)",
    )
