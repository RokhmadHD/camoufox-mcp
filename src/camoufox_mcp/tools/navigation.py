"""
NavigationService — handles all browser navigation tool requests.

Sits between the MCP tool layer and the browser/page helpers.
Each method validates input, delegates to browser helpers, and returns
a clean structured result dict safe to send to MCP clients.

Tool flow:
    browser_open / browser_back / browser_forward / browser_reload
        ↓
    NavigationService
        ↓
    BrowserManager (get_active_page)
        ↓
    browser/page.py helpers
        ↓
    Playwright Page
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from camoufox_mcp.browser.manager import BrowserManager
from camoufox_mcp.browser.page import go_back, go_forward, navigate_to, reload_page
from camoufox_mcp.utils.errors import SecurityError
from camoufox_mcp.utils.logging import get_logger

logger = get_logger(__name__)

# Allowed URL schemes
_ALLOWED_SCHEMES = {"http", "https"}


class NavigationService:
    """
    Service layer for navigation operations.

    Args:
        browser: The shared BrowserManager instance.
    """

    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    # ------------------------------------------------------------------ #
    # browser_open
    # ------------------------------------------------------------------ #

    async def open(
        self,
        session_id: str,
        url: str,
        *,
        timeout: int | None = None,
        wait_until: str = "domcontentloaded",
    ) -> dict[str, Any]:
        """
        Navigate the active page in a session to a URL.

        Args:
            session_id: Target session.
            url:        Destination URL. Must be http:// or https://.
            timeout:    Override navigation timeout (ms).
            wait_until: Playwright load-state strategy.

        Returns:
            Dict with success, session_id, url, title, status.

        Raises:
            SecurityError:   If the URL scheme is not allowed.
            NavigationError: If navigation fails.
        """
        _validate_url(url)

        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.navigation_timeout

        page = await self._browser.get_active_page(session_id)
        result = await navigate_to(page, url, timeout=_timeout, wait_until=wait_until)

        logger.info(
            "Navigated",
            extra={
                "session_id": session_id,
                "tool": "browser_open",
                "url": result["url"],
            },
        )
        return {
            "success": True,
            "session_id": session_id,
            **result,
        }

    # ------------------------------------------------------------------ #
    # browser_back
    # ------------------------------------------------------------------ #

    async def back(
        self,
        session_id: str,
        *,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Navigate back in the browser history."""
        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.navigation_timeout

        page = await self._browser.get_active_page(session_id)
        result = await go_back(page, timeout=_timeout)

        logger.info(
            "Navigated back",
            extra={"session_id": session_id, "tool": "browser_back", "url": result["url"]},
        )
        return {"success": True, "session_id": session_id, **result}

    # ------------------------------------------------------------------ #
    # browser_forward
    # ------------------------------------------------------------------ #

    async def forward(
        self,
        session_id: str,
        *,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Navigate forward in the browser history."""
        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.navigation_timeout

        page = await self._browser.get_active_page(session_id)
        result = await go_forward(page, timeout=_timeout)

        logger.info(
            "Navigated forward",
            extra={"session_id": session_id, "tool": "browser_forward", "url": result["url"]},
        )
        return {"success": True, "session_id": session_id, **result}

    # ------------------------------------------------------------------ #
    # browser_reload
    # ------------------------------------------------------------------ #

    async def reload(
        self,
        session_id: str,
        *,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Reload the current page."""
        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.navigation_timeout

        page = await self._browser.get_active_page(session_id)
        result = await reload_page(page, timeout=_timeout)

        logger.info(
            "Page reloaded",
            extra={"session_id": session_id, "tool": "browser_reload", "url": result["url"]},
        )
        return {"success": True, "session_id": session_id, **result}


# --------------------------------------------------------------------------- #
# URL validation helper
# --------------------------------------------------------------------------- #


def _validate_url(url: str) -> None:
    """
    Raise SecurityError if the URL is not a safe navigatable URL.

    Allows only http:// and https:// schemes.

    Args:
        url: URL string to validate.

    Raises:
        SecurityError: If the scheme is not allowed or the URL is malformed.
    """
    if not url or not isinstance(url, str):
        raise SecurityError("URL must be a non-empty string.")
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise SecurityError(f"Malformed URL '{url}': {exc}") from exc

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise SecurityError(
            f"URL scheme '{parsed.scheme}' is not allowed. "
            "Only http:// and https:// URLs are permitted."
        )
    if not parsed.netloc:
        raise SecurityError(f"URL '{url}' has no host component.")
