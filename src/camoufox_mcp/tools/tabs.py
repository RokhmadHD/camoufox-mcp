"""
TabService — handles all tab management tool requests.

Tool flow:
    browser_tabs / browser_new_tab / browser_close_tab / browser_switch_tab
        ↓
    TabService
        ↓
    BrowserManager (get_context)
        ↓
    browser/tabs.py helpers
        ↓
    Playwright BrowserContext / Page
"""

from __future__ import annotations

from typing import Any

from camoufox_mcp.browser.manager import BrowserManager
from camoufox_mcp.browser.tabs import close_tab, list_tabs, open_new_tab, switch_tab
from camoufox_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class TabService:
    """
    Service layer for tab management operations.

    Args:
        browser: The shared BrowserManager instance.
    """

    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    # ------------------------------------------------------------------ #
    # browser_tabs
    # ------------------------------------------------------------------ #

    async def get_tabs(self, session_id: str) -> dict[str, Any]:
        """
        List all open tabs in a session.

        Args:
            session_id: Target session.

        Returns:
            Dict with success, session_id, tabs list, count, active_tab_id.
        """
        session = self._browser.get_session(session_id)
        session.touch()
        context = self._browser.get_context(session_id)
        tabs_info = await list_tabs(context, session_id)

        logger.info(
            "Listed tabs",
            extra={"session_id": session_id, "tool": "browser_tabs", "count": tabs_info.count},
        )
        return {
            "success": True,
            "session_id": session_id,
            "count": tabs_info.count,
            "active_tab_id": tabs_info.active_tab_id,
            "tabs": [t.model_dump() for t in tabs_info.tabs],
        }

    # ------------------------------------------------------------------ #
    # browser_new_tab
    # ------------------------------------------------------------------ #

    async def new_tab(
        self,
        session_id: str,
        url: str | None = None,
    ) -> dict[str, Any]:
        """
        Open a new tab in a session, optionally navigating to a URL.

        Args:
            session_id: Target session.
            url:        Optional URL to open in the new tab.

        Returns:
            Dict with success, session_id, page_id, url.
        """
        from camoufox_mcp.browser.context import _page_id

        session = self._browser.get_session(session_id)
        session.touch()
        context = self._browser.get_context(session_id)

        if url:
            from camoufox_mcp.tools.navigation import _validate_url

            _validate_url(url)

        page = await open_new_tab(context, url=url)
        pid = _page_id(page)

        logger.info(
            "Opened new tab",
            extra={
                "session_id": session_id,
                "tool": "browser_new_tab",
                "page_id": pid,
                "url": page.url,
            },
        )
        return {
            "success": True,
            "session_id": session_id,
            "page_id": pid,
            "url": page.url,
            "message": f"New tab opened. page_id='{pid}'",
        }

    # ------------------------------------------------------------------ #
    # browser_close_tab
    # ------------------------------------------------------------------ #

    async def close_tab(
        self,
        session_id: str,
        page_id: str,
    ) -> dict[str, Any]:
        """
        Close a specific tab by page_id.

        Args:
            session_id: Target session.
            page_id:    ID of the tab to close.

        Returns:
            Dict with success, session_id, closed_page_id, remaining_tabs.
        """
        session = self._browser.get_session(session_id)
        session.touch()
        context = self._browser.get_context(session_id)

        result = await close_tab(context, page_id)

        logger.info(
            "Closed tab",
            extra={
                "session_id": session_id,
                "tool": "browser_close_tab",
                "page_id": page_id,
                "remaining": result["remaining_tabs"],
            },
        )
        return {
            "success": True,
            "session_id": session_id,
            **result,
            "message": f"Tab '{page_id}' closed. {result['remaining_tabs']} tab(s) remaining.",
        }

    # ------------------------------------------------------------------ #
    # browser_switch_tab
    # ------------------------------------------------------------------ #

    async def switch_tab(
        self,
        session_id: str,
        page_id: str,
    ) -> dict[str, Any]:
        """
        Switch the active tab in a session.

        Args:
            session_id: Target session.
            page_id:    ID of the tab to switch to.

        Returns:
            Dict with success, session_id, page_id, url, title.
        """
        session = self._browser.get_session(session_id)
        session.touch()
        context = self._browser.get_context(session_id)

        page = await switch_tab(context, page_id)
        title = await page.title()

        logger.info(
            "Switched tab",
            extra={
                "session_id": session_id,
                "tool": "browser_switch_tab",
                "page_id": page_id,
                "url": page.url,
            },
        )
        return {
            "success": True,
            "session_id": session_id,
            "page_id": page_id,
            "url": page.url,
            "title": title,
            "message": f"Switched to tab '{page_id}'.",
        }
