"""Extraction engine for Camoufox MCP."""

from camoufox_mcp.extraction.html import extract_html
from camoufox_mcp.extraction.structured import (
    extract_headings,
    extract_links,
    extract_metadata,
    extract_tables,
)
from camoufox_mcp.extraction.text import extract_text

__all__ = [
    "extract_html",
    "extract_text",
    "extract_links",
    "extract_metadata",
    "extract_tables",
    "extract_headings",
]
