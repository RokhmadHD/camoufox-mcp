"""
Plain text extraction from a Playwright Page.

Extracts the visible text content of a page using innerText, which respects
CSS visibility rules and excludes script/style element content.

Size limits are enforced to prevent enormous payloads from being returned
to MCP clients.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from camoufox_mcp.utils.errors import BrowserError
from camoufox_mcp.utils.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = get_logger(__name__)

# JavaScript that extracts clean visible text from the page body.
# Uses innerText which:
#   - respects CSS display/visibility
#   - strips script/style content automatically
#   - normalises whitespace (browser-level)
_EXTRACT_TEXT_JS = """
() => {
    const body = document.body;
    if (!body) return '';
    // innerText gives us visible text only
    return body.innerText || '';
}
"""

# Fallback JS for textContent (less clean but more compatible)
_EXTRACT_TEXT_FALLBACK_JS = """
() => {
    const scripts = document.querySelectorAll('script, style, noscript');
    scripts.forEach(el => el.remove());
    return document.body ? document.body.textContent : '';
}
"""


async def extract_text(
    page: Page,
    *,
    max_length: int = 50_000,
    selector: str | None = None,
) -> dict[str, Any]:
    """
    Extract visible text from a page or a specific element.

    Args:
        page:       The Playwright Page.
        max_length: Maximum number of characters to return.
        selector:   Optional CSS selector to limit extraction to one element.
                    If None, extracts from the full page body.

    Returns:
        Dict with text, truncated, char_count, url, title.

    Raises:
        BrowserError: If extraction fails.
    """
    try:
        url = page.url
        title = await page.title()

        if selector:
            # Extract text from a specific element
            try:
                element = page.locator(selector).first
                raw_text = await element.inner_text(timeout=10_000)
            except Exception as exc:
                raise BrowserError(
                    f"Failed to extract text from selector '{selector}': {exc}"
                ) from exc
        else:
            # Extract full page text
            try:
                raw_text = await page.evaluate(_EXTRACT_TEXT_JS)
            except Exception:
                # Fallback if innerText is unavailable
                raw_text = await page.evaluate(_EXTRACT_TEXT_FALLBACK_JS)

        if not isinstance(raw_text, str):
            raw_text = ""

        # Normalise whitespace — collapse multiple blank lines
        import re

        raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)
        raw_text = raw_text.strip()

        truncated = len(raw_text) > max_length
        text = raw_text[:max_length] if truncated else raw_text

        logger.debug(
            "Text extracted",
            extra={
                "url": url,
                "chars": len(text),
                "truncated": truncated,
            },
        )

        return {
            "url": url,
            "title": title,
            "text": text,
            "char_count": len(text),
            "truncated": truncated,
            "selector": selector,
        }

    except BrowserError:
        raise
    except Exception as exc:
        raise BrowserError(f"Text extraction failed: {exc}") from exc
