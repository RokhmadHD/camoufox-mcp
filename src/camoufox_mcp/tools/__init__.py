"""MCP tool service layer for Camoufox MCP."""

from camoufox_mcp.tools.downloads import DownloadService
from camoufox_mcp.tools.extraction import ExtractionService
from camoufox_mcp.tools.interaction import InteractionService
from camoufox_mcp.tools.javascript import JavaScriptService
from camoufox_mcp.tools.navigation import NavigationService
from camoufox_mcp.tools.screenshot import ScreenshotService
from camoufox_mcp.tools.sessions import SessionService
from camoufox_mcp.tools.tabs import TabService
from camoufox_mcp.tools.wait import WaitService

__all__ = [
    "DownloadService",
    "ExtractionService",
    "InteractionService",
    "JavaScriptService",
    "NavigationService",
    "ScreenshotService",
    "SessionService",
    "TabService",
    "WaitService",
]
