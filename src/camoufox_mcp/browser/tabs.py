"""
Tab tracking utilities for a Playwright BrowserContext.

In Playwright/Camoufox, tabs are just Page objects within a BrowserContext.
This module provides helpers to list, identify, open, close, and switch tabs
within a session context.

We identify tabs by a stable string ID derived from ``id(page)`` (hex),
rather than by index (which would shift on close).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from camoufox_mcp.browser.context import _page_id, get_page_by_id
from camoufox_mcp.models.page import PageInfo, TabsInfo
from camoufox_mcp.utils.errors import BrowserError
from camoufox_mcp.utils.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

logger = get_logger(__name__)


def _build_page_info(page: Page, session_id: str, active_id: str | None = None) -> PageInfo:
    pid = _page_id(page)
    return PageInfo(
        page_id=pid,
        session_id=session_id,
        url=page.url,
        title="",  # title is async — caller fills this in
        is_active=(pid == active_id),
    )


async def list_tabs(context: BrowserContext, session_id: str) -> TabsInfo:
    """
    Return a TabsInfo snapshot of all open pages in the context.

    Args:
        context:    The BrowserContext.
        session_id: Session this context belongs to.

    Returns:
        TabsInfo with all open tabs and the active tab id.
    """
    pages = context.pages
    active_id = _page_id(pages[-1]) if pages else None

    tabs: list[PageInfo] = []
    for page in pages:
        pid = _page_id(page)
        try:
            title = await page.title()
        except Exception:  # noqa: BLE001
            title = ""
        tabs.append(
            PageInfo(
                page_id=pid,
                session_id=session_id,
                url=page.url,
                title=title,
                is_active=(pid == active_id),
            )
        )

    return TabsInfo(
        session_id=session_id,
        tabs=tabs,
        active_tab_id=active_id,
    )


async def open_new_tab(
    context: BrowserContext,
    url: str | None = None,
) -> Page:
    """
    Open a new blank tab (and optionally navigate to a URL).

    Args:
        context: The BrowserContext.
        url:     Optional URL to navigate to after opening.

    Returns:
        The new Page object.

    Raises:
        BrowserError: If the page cannot be created.
    """
    try:
        page = await context.new_page()
    except Exception as exc:
        raise BrowserError(f"Failed to open new tab: {exc}") from exc

    if url:
        await page.goto(url, wait_until="domcontentloaded")

    logger.debug("Opened new tab", extra={"page_id": _page_id(page), "url": page.url})
    return page


async def close_tab(context: BrowserContext, page_id: str) -> dict[str, Any]:
    """
    Close a specific tab by page_id.

    Args:
        context: The BrowserContext.
        page_id: ID string of the page to close.

    Returns:
        Dict with closed page_id and remaining tab count.

    Raises:
        BrowserError: If page_id is not found or close fails.
    """
    page = await get_page_by_id(context, page_id)
    url = page.url
    try:
        await page.close()
    except Exception as exc:
        raise BrowserError(f"Failed to close tab '{page_id}': {exc}") from exc

    logger.debug("Closed tab", extra={"page_id": page_id, "url": url})
    return {"closed_page_id": page_id, "remaining_tabs": len(context.pages)}


async def switch_tab(context: BrowserContext, page_id: str) -> Page:
    """
    Switch to a tab by page_id by bringing it to the front.

    In headless mode this is a logical "active page" designation.
    In headful mode it calls page.bring_to_front().

    Args:
        context: The BrowserContext.
        page_id: ID string of the target page.

    Returns:
        The target Page object (now active).

    Raises:
        BrowserError: If page_id is not found.
    """
    import contextlib

    page = await get_page_by_id(context, page_id)
    with contextlib.suppress(Exception):
        await page.bring_to_front()

    # Re-order context.pages so this page is last (treated as active)
    # Playwright doesn't expose a direct re-order API, so we rely on
    # bring_to_front for headful and page_id-based addressing elsewhere.
    logger.debug("Switched to tab", extra={"page_id": page_id, "url": page.url})
    return page
