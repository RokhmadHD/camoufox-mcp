"""
HTML extraction from a Playwright Page.

Returns the outer HTML of the page or a specific element.
Size limits are strictly enforced — full HTML documents can be very large.

The caller decides the max_length; the default is conservative (200KB chars).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from camoufox_mcp.utils.errors import BrowserError
from camoufox_mcp.utils.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = get_logger(__name__)


async def extract_html(
    page: Page,
    *,
    max_length: int = 200_000,
    selector: str | None = None,
    outer: bool = True,
) -> dict[str, Any]:
    """
    Extract HTML from a page or a specific element.

    Args:
        page:       The Playwright Page.
        max_length: Maximum number of characters to return.
        selector:   Optional CSS selector to limit extraction to one element.
                    If None, extracts the full document HTML.
        outer:      If True, include the element's own tag (outerHTML).
                    If False, return only the element's children (innerHTML).

    Returns:
        Dict with html, truncated, char_count, url, title.

    Raises:
        BrowserError: If extraction fails.
    """
    try:
        url = page.url
        title = await page.title()

        if selector:
            try:
                locator = page.locator(selector).first
                if outer:
                    raw_html = await locator.evaluate("el => el.outerHTML", timeout=10_000)
                else:
                    raw_html = await locator.inner_html(timeout=10_000)
            except Exception as exc:
                raise BrowserError(
                    f"Failed to extract HTML from selector '{selector}': {exc}"
                ) from exc
        else:
            try:
                raw_html = await page.content()
            except Exception as exc:
                raise BrowserError(f"Failed to get page HTML content: {exc}") from exc

        if not isinstance(raw_html, str):
            raw_html = ""

        truncated = len(raw_html) > max_length
        html = raw_html[:max_length] if truncated else raw_html

        logger.debug(
            "HTML extracted",
            extra={
                "url": url,
                "chars": len(html),
                "truncated": truncated,
                "selector": selector,
            },
        )

        return {
            "url": url,
            "title": title,
            "html": html,
            "char_count": len(html),
            "truncated": truncated,
            "selector": selector,
        }

    except BrowserError:
        raise
    except Exception as exc:
        raise BrowserError(f"HTML extraction failed: {exc}") from exc
