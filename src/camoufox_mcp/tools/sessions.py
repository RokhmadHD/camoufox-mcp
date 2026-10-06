"""
SessionService — handles session-level information queries.

Provides the data behind tools like browser_sessions (Phase 1 already
registers a basic version; this service adds richer detail for Phase 2+).

Tool flow:
    browser_sessions / browser_session_info
        ↓
    SessionService
        ↓
    BrowserManager
"""

from __future__ import annotations

from typing import Any

from camoufox_mcp.browser.manager import BrowserManager
from camoufox_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class SessionService:
    """
    Service layer for session information and lifecycle.

    Args:
        browser: The shared BrowserManager instance.
    """

    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    async def list_sessions(self) -> dict[str, Any]:
        """Return all active sessions with full metadata."""
        sessions = self._browser.list_sessions()
        return {
            "success": True,
            "count": len(sessions),
            "sessions": [s.model_dump() for s in sessions],
        }

    async def get_session_info(self, session_id: str) -> dict[str, Any]:
        """
        Return detailed info for a single session.

        Args:
            session_id: Target session.

        Returns:
            Dict with session metadata and open tabs.

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        session = self._browser.get_session(session_id)
        info = session.to_info()

        # Enrich with tab list
        from camoufox_mcp.browser.tabs import list_tabs

        context = self._browser.get_context(session_id)
        tabs_info = await list_tabs(context, session_id)

        return {
            "success": True,
            **info.model_dump(),
            "tabs": [t.model_dump() for t in tabs_info.tabs],
        }
