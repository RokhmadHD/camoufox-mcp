"""
Page helpers — utilities that operate on a single Playwright Page.

These functions wrap common Playwright page operations with:
  - consistent error translation to our custom exceptions
  - logging
  - sensible defaults

They are called by services and never exposed to MCP directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from camoufox_mcp.utils.errors import BrowserError, NavigationError, TimeoutError
from camoufox_mcp.utils.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = get_logger(__name__)


async def navigate_to(
    page: Page,
    url: str,
    *,
    timeout: int = 30_000,
    wait_until: str = "domcontentloaded",
) -> dict[str, Any]:
    """
    Navigate the page to a URL and return basic page metadata.

    Args:
        page:       The Playwright Page.
        url:        Destination URL (must start with http:// or https://).
        timeout:    Navigation timeout in milliseconds.
        wait_until: Playwright load-state to wait for.

    Returns:
        Dict with url, title, status.

    Raises:
        NavigationError: If navigation fails.
        TimeoutError:    If the navigation timeout is exceeded.
    """
    logger.debug("Navigating", extra={"url": url, "wait_until": wait_until})
    try:
        response = await page.goto(url, timeout=timeout, wait_until=wait_until)
        title = await page.title()
        status = response.status if response else None
        return {"url": page.url, "title": title, "status": status}
    except Exception as exc:
        msg = str(exc).lower()
        if "timeout" in msg:
            raise TimeoutError(f"navigation to {url}", timeout) from exc
        raise NavigationError(url, str(exc)) from exc


async def go_back(page: Page, *, timeout: int = 30_000) -> dict[str, Any]:
    """Navigate back in the browser history."""
    try:
        await page.go_back(timeout=timeout, wait_until="domcontentloaded")
        return {"url": page.url, "title": await page.title()}
    except Exception as exc:
        if "timeout" in str(exc).lower():
            raise TimeoutError("browser_back", timeout) from exc
        raise NavigationError(page.url, f"go_back failed: {exc}") from exc


async def go_forward(page: Page, *, timeout: int = 30_000) -> dict[str, Any]:
    """Navigate forward in the browser history."""
    try:
        await page.go_forward(timeout=timeout, wait_until="domcontentloaded")
        return {"url": page.url, "title": await page.title()}
    except Exception as exc:
        if "timeout" in str(exc).lower():
            raise TimeoutError("browser_forward", timeout) from exc
        raise NavigationError(page.url, f"go_forward failed: {exc}") from exc


async def reload_page(page: Page, *, timeout: int = 30_000) -> dict[str, Any]:
    """Reload the current page."""
    try:
        await page.reload(timeout=timeout, wait_until="domcontentloaded")
        return {"url": page.url, "title": await page.title()}
    except Exception as exc:
        if "timeout" in str(exc).lower():
            raise TimeoutError("browser_reload", timeout) from exc
        raise NavigationError(page.url, f"reload failed: {exc}") from exc


async def get_page_info(page: Page) -> dict[str, Any]:
    """Return current URL and title of a page without triggering navigation."""
    try:
        return {"url": page.url, "title": await page.title()}
    except Exception as exc:
        raise BrowserError(f"Failed to read page info: {exc}") from exc
