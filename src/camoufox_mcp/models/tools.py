"""
Shared tool result models.

All MCP tools return a dict derived from one of these models.
Never return raw internal objects to the MCP layer.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Generic result envelope for any MCP tool."""

    success: bool
    message: str | None = None
    data: dict[str, Any] | None = None
    error: str | None = None

    @classmethod
    def ok(
        cls,
        message: str | None = None,
        **data: Any,
    ) -> ToolResult:
        """Convenience constructor for a successful result."""
        return cls(
            success=True,
            message=message,
            data=data or None,
        )

    @classmethod
    def fail(cls, error: str, message: str | None = None) -> ToolResult:
        """Convenience constructor for a failed result."""
        return cls(success=False, error=error, message=message)


class NavigationResult(BaseModel):
    """Result returned by navigation tools (browser_open, browser_reload, etc.)."""

    success: bool
    session_id: str
    url: str
    title: str
    status: int | None = Field(default=None, description="HTTP status code if available")
    error: str | None = None


class ExtractionResult(BaseModel):
    """Result returned by extraction tools (browser_extract_text, browser_extract_html)."""

    success: bool
    session_id: str
    url: str
    title: str
    content: str
    truncated: bool = False
    content_length: int = 0
    error: str | None = None

    def model_post_init(self, __context: object) -> None:
        self.content_length = len(self.content)


class ScreenshotResult(BaseModel):
    """Result returned by browser_screenshot."""

    success: bool
    session_id: str
    path: str
    filename: str
    width: int | None = None
    height: int | None = None
    error: str | None = None
