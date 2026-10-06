"""
ExtractionService — handles all content extraction tool requests.

Tool flow:
    browser_extract_text / browser_extract_html /
    browser_extract_links / browser_extract_metadata /
    browser_extract_tables / browser_extract_headings
        ↓
    ExtractionService
        ↓
    BrowserManager (get_active_page)
        ↓
    extraction/text.py | html.py | structured.py
        ↓
    Playwright Page (JS evaluation)
"""

from __future__ import annotations

from typing import Any

from camoufox_mcp.browser.manager import BrowserManager
from camoufox_mcp.extraction.html import extract_html
from camoufox_mcp.extraction.structured import (
    extract_headings,
    extract_links,
    extract_metadata,
    extract_tables,
)
from camoufox_mcp.extraction.text import extract_text
from camoufox_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class ExtractionService:
    """
    Service layer for content extraction operations.

    Args:
        browser: The shared BrowserManager instance.
    """

    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    # ------------------------------------------------------------------ #
    # browser_extract_text
    # ------------------------------------------------------------------ #

    async def get_text(
        self,
        session_id: str,
        *,
        max_length: int | None = None,
        selector: str | None = None,
    ) -> dict[str, Any]:
        """
        Extract visible text from the current page.

        Args:
            session_id: Target session.
            max_length: Override default max text length.
            selector:   Optional CSS selector to limit extraction scope.

        Returns:
            Dict with success, session_id, url, title, text, char_count, truncated.
        """
        session = self._browser.get_session(session_id)
        session.touch()
        _max = max_length or self._browser._settings.max_text_length

        page = await self._browser.get_active_page(session_id)
        result = await extract_text(page, max_length=_max, selector=selector)

        logger.info(
            "Text extracted",
            extra={
                "session_id": session_id,
                "tool": "browser_extract_text",
                "url": result["url"],
                "chars": result["char_count"],
                "truncated": result["truncated"],
            },
        )
        return {"success": True, "session_id": session_id, **result}

    # ------------------------------------------------------------------ #
    # browser_extract_html
    # ------------------------------------------------------------------ #

    async def get_html(
        self,
        session_id: str,
        *,
        max_length: int | None = None,
        selector: str | None = None,
        outer: bool = True,
    ) -> dict[str, Any]:
        """
        Extract HTML from the current page or a specific element.

        Args:
            session_id: Target session.
            max_length: Override default max HTML length.
            selector:   Optional CSS selector to limit extraction scope.
            outer:      Return outerHTML (True) or innerHTML (False).

        Returns:
            Dict with success, session_id, url, title, html, char_count, truncated.
        """
        session = self._browser.get_session(session_id)
        session.touch()
        _max = max_length or self._browser._settings.max_html_length

        page = await self._browser.get_active_page(session_id)
        result = await extract_html(page, max_length=_max, selector=selector, outer=outer)

        logger.info(
            "HTML extracted",
            extra={
                "session_id": session_id,
                "tool": "browser_extract_html",
                "url": result["url"],
                "chars": result["char_count"],
                "truncated": result["truncated"],
            },
        )
        return {"success": True, "session_id": session_id, **result}

    # ------------------------------------------------------------------ #
    # browser_extract_links
    # ------------------------------------------------------------------ #

    async def get_links(
        self,
        session_id: str,
        *,
        max_links: int = 200,
    ) -> dict[str, Any]:
        """
        Extract all hyperlinks from the current page.

        Args:
            session_id: Target session.
            max_links:  Maximum number of links to return.

        Returns:
            Dict with success, session_id, url, title, links, link_count.
        """
        session = self._browser.get_session(session_id)
        session.touch()

        page = await self._browser.get_active_page(session_id)
        result = await extract_links(page, max_links=max_links)

        logger.info(
            "Links extracted",
            extra={
                "session_id": session_id,
                "tool": "browser_extract_links",
                "url": result["url"],
                "count": result["link_count"],
            },
        )
        return {"success": True, "session_id": session_id, **result}

    # ------------------------------------------------------------------ #
    # browser_extract_metadata
    # ------------------------------------------------------------------ #

    async def get_metadata(self, session_id: str) -> dict[str, Any]:
        """
        Extract page metadata (title, description, OG tags, etc.).

        Args:
            session_id: Target session.

        Returns:
            Dict with success, session_id, url, title, metadata.
        """
        session = self._browser.get_session(session_id)
        session.touch()

        page = await self._browser.get_active_page(session_id)
        result = await extract_metadata(page)

        logger.info(
            "Metadata extracted",
            extra={
                "session_id": session_id,
                "tool": "browser_extract_metadata",
                "url": result["url"],
            },
        )
        return {"success": True, "session_id": session_id, **result}

    # ------------------------------------------------------------------ #
    # browser_extract_tables
    # ------------------------------------------------------------------ #

    async def get_tables(
        self,
        session_id: str,
        *,
        max_tables: int = 20,
    ) -> dict[str, Any]:
        """
        Extract all HTML tables from the current page.

        Args:
            session_id: Target session.
            max_tables: Maximum number of tables to return.

        Returns:
            Dict with success, session_id, url, title, tables, table_count.
        """
        session = self._browser.get_session(session_id)
        session.touch()

        page = await self._browser.get_active_page(session_id)
        result = await extract_tables(page, max_tables=max_tables)

        logger.info(
            "Tables extracted",
            extra={
                "session_id": session_id,
                "tool": "browser_extract_tables",
                "url": result["url"],
                "count": result["table_count"],
            },
        )
        return {"success": True, "session_id": session_id, **result}

    # ------------------------------------------------------------------ #
    # browser_extract_headings
    # ------------------------------------------------------------------ #

    async def get_headings(self, session_id: str) -> dict[str, Any]:
        """
        Extract all headings (h1–h6) from the current page.

        Args:
            session_id: Target session.

        Returns:
            Dict with success, session_id, url, title, headings, heading_count.
        """
        session = self._browser.get_session(session_id)
        session.touch()

        page = await self._browser.get_active_page(session_id)
        result = await extract_headings(page)

        logger.info(
            "Headings extracted",
            extra={
                "session_id": session_id,
                "tool": "browser_extract_headings",
                "url": result["url"],
            },
        )
        return {"success": True, "session_id": session_id, **result}
