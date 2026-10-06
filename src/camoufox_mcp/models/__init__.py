"""Pydantic models for Camoufox MCP."""

from camoufox_mcp.models.browser import BrowserInfo, ContextOptions
from camoufox_mcp.models.page import PageInfo, TabsInfo
from camoufox_mcp.models.session import (
    CloseSessionRequest,
    CreateSessionRequest,
    SessionInfo,
    SessionStatus,
)
from camoufox_mcp.models.tools import (
    ExtractionResult,
    NavigationResult,
    ScreenshotResult,
    ToolResult,
)

__all__ = [
    "BrowserInfo",
    "ContextOptions",
    "PageInfo",
    "TabsInfo",
    "SessionInfo",
    "SessionStatus",
    "CreateSessionRequest",
    "CloseSessionRequest",
    "ToolResult",
    "NavigationResult",
    "ExtractionResult",
    "ScreenshotResult",
]
