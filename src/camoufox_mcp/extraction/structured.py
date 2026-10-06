"""
Structured data extraction from a Playwright Page.

Extracts:
  - links         (<a href>) with text and absolute URLs
  - metadata      (<meta> tags, title, canonical URL, Open Graph, etc.)
  - tables        (<table> elements as list-of-rows)
  - headings      (h1–h6 with level and text)

All extraction is done via JavaScript evaluation to avoid relying on
BeautifulSoup or other heavy HTML parsers as dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from camoufox_mcp.utils.errors import BrowserError
from camoufox_mcp.utils.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = get_logger(__name__)

# --------------------------------------------------------------------------- #
# JavaScript extraction helpers
# --------------------------------------------------------------------------- #

_EXTRACT_LINKS_JS = """
() => {
    const links = [];
    for (const a of document.querySelectorAll('a[href]')) {
        const href = a.href;          // already absolute (browser resolves it)
        const text = (a.innerText || a.textContent || '').trim().slice(0, 200);
        const rel  = a.getAttribute('rel') || '';
        if (href && !href.startsWith('javascript:')) {
            links.push({ href, text, rel });
        }
    }
    return links;
}
"""

_EXTRACT_METADATA_JS = """
() => {
    const meta = {};

    // Basic
    meta.title = document.title || '';
    meta.url   = location.href;

    // Canonical
    const canonical = document.querySelector('link[rel="canonical"]');
    if (canonical) meta.canonical = canonical.href;

    // Description
    const desc = document.querySelector('meta[name="description"]');
    if (desc) meta.description = desc.content;

    // Keywords
    const kw = document.querySelector('meta[name="keywords"]');
    if (kw) meta.keywords = kw.content;

    // Author
    const author = document.querySelector('meta[name="author"]');
    if (author) meta.author = author.content;

    // Open Graph
    const og = {};
    for (const m of document.querySelectorAll('meta[property^="og:"]')) {
        const key = m.getAttribute('property').replace('og:', '');
        og[key] = m.content;
    }
    if (Object.keys(og).length) meta.og = og;

    // Twitter Card
    const tw = {};
    for (const m of document.querySelectorAll('meta[name^="twitter:"]')) {
        const key = m.getAttribute('name').replace('twitter:', '');
        tw[key] = m.content;
    }
    if (Object.keys(tw).length) meta.twitter = tw;

    // Robots
    const robots = document.querySelector('meta[name="robots"]');
    if (robots) meta.robots = robots.content;

    // Language
    meta.lang = document.documentElement.lang || '';

    return meta;
}
"""

_EXTRACT_TABLES_JS = """
() => {
    const tables = [];
    for (const table of document.querySelectorAll('table')) {
        const rows = [];
        // Try thead first, then all tr elements
        const allRows = table.querySelectorAll('tr');
        for (const tr of allRows) {
            const cells = [];
            for (const cell of tr.querySelectorAll('th, td')) {
                cells.push((cell.innerText || cell.textContent || '').trim().slice(0, 500));
            }
            if (cells.length > 0) {
                rows.push(cells);
            }
        }
        if (rows.length > 0) {
            const caption = table.querySelector('caption');
            tables.push({
                caption: caption ? (caption.innerText || '').trim() : null,
                rows: rows,
                row_count: rows.length,
                col_count: Math.max(...rows.map(r => r.length)),
            });
        }
    }
    return tables;
}
"""

_EXTRACT_HEADINGS_JS = """
() => {
    const headings = [];
    for (const el of document.querySelectorAll('h1,h2,h3,h4,h5,h6')) {
        const level = parseInt(el.tagName[1]);
        const text = (el.innerText || el.textContent || '').trim().slice(0, 300);
        if (text) headings.push({ level, text });
    }
    return headings;
}
"""


# --------------------------------------------------------------------------- #
# Extraction functions
# --------------------------------------------------------------------------- #


async def extract_links(
    page: Page,
    *,
    max_links: int = 200,
) -> dict[str, Any]:
    """
    Extract all hyperlinks from the page.

    Args:
        page:      The Playwright Page.
        max_links: Maximum number of links to return.

    Returns:
        Dict with url, title, links (list), link_count.

    Raises:
        BrowserError: If extraction fails.
    """
    try:
        url = page.url
        title = await page.title()
        raw_links: list[dict[str, str]] = await page.evaluate(_EXTRACT_LINKS_JS)

        if not isinstance(raw_links, list):
            raw_links = []

        truncated = len(raw_links) > max_links
        links = raw_links[:max_links]

        logger.debug(
            "Links extracted",
            extra={"url": url, "count": len(links), "truncated": truncated},
        )

        return {
            "url": url,
            "title": title,
            "links": links,
            "link_count": len(links),
            "truncated": truncated,
        }

    except BrowserError:
        raise
    except Exception as exc:
        raise BrowserError(f"Link extraction failed: {exc}") from exc


async def extract_metadata(page: Page) -> dict[str, Any]:
    """
    Extract page metadata (title, description, OG tags, etc.).

    Args:
        page: The Playwright Page.

    Returns:
        Dict with url, title, metadata dict.

    Raises:
        BrowserError: If extraction fails.
    """
    try:
        url = page.url
        raw: dict[str, Any] = await page.evaluate(_EXTRACT_METADATA_JS)

        if not isinstance(raw, dict):
            raw = {}

        logger.debug("Metadata extracted", extra={"url": url})

        return {
            "url": url,
            "title": raw.get("title", ""),
            "metadata": raw,
        }

    except BrowserError:
        raise
    except Exception as exc:
        raise BrowserError(f"Metadata extraction failed: {exc}") from exc


async def extract_tables(
    page: Page,
    *,
    max_tables: int = 20,
) -> dict[str, Any]:
    """
    Extract all HTML tables from the page.

    Args:
        page:       The Playwright Page.
        max_tables: Maximum number of tables to return.

    Returns:
        Dict with url, title, tables (list), table_count.

    Raises:
        BrowserError: If extraction fails.
    """
    try:
        url = page.url
        title = await page.title()
        raw_tables: list[dict[str, Any]] = await page.evaluate(_EXTRACT_TABLES_JS)

        if not isinstance(raw_tables, list):
            raw_tables = []

        truncated = len(raw_tables) > max_tables
        tables = raw_tables[:max_tables]

        logger.debug(
            "Tables extracted",
            extra={"url": url, "count": len(tables)},
        )

        return {
            "url": url,
            "title": title,
            "tables": tables,
            "table_count": len(tables),
            "truncated": truncated,
        }

    except BrowserError:
        raise
    except Exception as exc:
        raise BrowserError(f"Table extraction failed: {exc}") from exc


async def extract_headings(page: Page) -> dict[str, Any]:
    """
    Extract all headings (h1–h6) from the page.

    Args:
        page: The Playwright Page.

    Returns:
        Dict with url, title, headings list.

    Raises:
        BrowserError: If extraction fails.
    """
    try:
        url = page.url
        title = await page.title()
        headings: list[dict[str, Any]] = await page.evaluate(_EXTRACT_HEADINGS_JS)

        if not isinstance(headings, list):
            headings = []

        return {
            "url": url,
            "title": title,
            "headings": headings,
            "heading_count": len(headings),
        }

    except BrowserError:
        raise
    except Exception as exc:
        raise BrowserError(f"Heading extraction failed: {exc}") from exc
