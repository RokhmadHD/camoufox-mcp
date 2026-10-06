"""
Context helpers — utilities that operate on a Playwright BrowserContext.

These are pure helper functions, not a class.
They are called by services (NavigationService, TabService, etc.) and
never exposed directly to MCP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from camoufox_mcp.utils.errors import BrowserError
from camoufox_mcp.utils.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

logger = get_logger(__name__)


async def get_page_by_id(context: BrowserContext, page_id: str) -> Page:
    """
    Return a page from the context that matches the given page_id.

    page_id is derived from ``id(page)`` cast to hex string.

    Args:
        context: The Playwright BrowserContext.
        page_id: Hex string ID of the target page.

    Returns:
        The matching Page object.

    Raises:
        BrowserError: If no page with that ID exists in the context.
    """
    for page in context.pages:
        if _page_id(page) == page_id:
            return page
    raise BrowserError(
        f"No page with id '{page_id}' found in the current session. "
        "It may have been closed. Use browser_tabs to list open tabs."
    )


def _page_id(page: Page) -> str:
    """Derive a stable string ID from a Page object."""
    return hex(id(page))


def get_active_page_from_context(context: BrowserContext) -> Page | None:
    """
    Return the last page in the context (treated as the active tab).

    Returns None if no pages exist.
    """
    pages = context.pages
    return pages[-1] if pages else None


async def ensure_page(context: BrowserContext) -> Page:
    """
    Return the active page, creating a new one if the context has none.

    Args:
        context: The Playwright BrowserContext.

    Returns:
        An open Page object.

    Raises:
        BrowserError: If a new page cannot be created.
    """
    page = get_active_page_from_context(context)
    if page is not None:
        return page
    try:
        return await context.new_page()
    except Exception as exc:
        raise BrowserError(f"Failed to create a new page: {exc}") from exc


def list_page_ids(context: BrowserContext) -> list[str]:
    """Return a list of page IDs for all open pages in the context."""
    return [_page_id(p) for p in context.pages]
