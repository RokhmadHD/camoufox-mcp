"""
Session-related Pydantic models.

A Session is the top-level unit that an MCP tool operates against.
It groups a browser context, pages, profile name, and metadata.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    CREATING = "creating"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


class SessionInfo(BaseModel):
    """Serialisable snapshot of a session — safe to return to MCP clients."""

    session_id: str
    status: SessionStatus
    profile: str
    headless: bool
    created_at: datetime
    last_activity: datetime
    page_count: int = 0
    active_url: str | None = None

    model_config = {"use_enum_values": True}


class CreateSessionRequest(BaseModel):
    """Input for browser_launch tool."""

    profile: str = Field(default="default", description="Profile name to use")
    headless: bool = Field(default=True, description="Run headless")
    humanize: bool = Field(default=False, description="Enable humanize mode")
    extra_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional Camoufox launch options (advanced use)",
    )


class CloseSessionRequest(BaseModel):
    """Input for browser_close tool."""

    session_id: str = Field(description="Session to close")
