"""
Selector resolution — translates a ParsedSelector into a Playwright Locator.

This bridges the security/validation layer (which only parses strings) and
the actual Playwright API (which uses page.locator(), page.get_by_role(), etc.).

The separation allows:
  - validation to be tested without a browser
  - resolution logic to be changed (e.g. prefer get_by_role over CSS) without
    touching validation
  - future support for fallback strategies

Usage:
    from camoufox_mcp.security.validation import parse_selector
    from camoufox_mcp.browser.selector import resolve_locator

    parsed = parse_selector("role=button[name='Submit']")
    locator = resolve_locator(page, parsed)
    await locator.click()
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from camoufox_mcp.security.validation import ParsedSelector
from camoufox_mcp.utils.errors import SelectorError
from camoufox_mcp.utils.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

logger = get_logger(__name__)


def resolve_locator(page: Page, parsed: ParsedSelector) -> Locator:
    """
    Convert a ParsedSelector into a Playwright Locator.

    Uses the most semantically appropriate Playwright API for each type:
      - role  → page.get_by_role()
      - label → page.get_by_label()
      - placeholder → page.get_by_placeholder()
      - text  → page.get_by_text()
      - xpath → page.locator("xpath=...")
      - id    → page.locator("#id")
      - testid → page.get_by_test_id()
      - css   → page.locator(selector)

    Args:
        page:   The Playwright Page.
        parsed: A ParsedSelector from parse_selector().

    Returns:
        A Playwright Locator (not yet resolved — resolution is lazy).

    Raises:
        SelectorError: If the selector type is not supported.
    """
    stype = parsed.selector_type
    value = parsed.value

    try:
        match stype:
            case "role":
                # value may include name filter: "button" or "button[name='Submit']"
                role_name, _, attrs = value.partition("[")
                role_name = role_name.strip()
                if attrs:
                    # Extract name= attribute if present
                    import re

                    name_match = re.search(r"name=['\"]?([^'\"\\]]+)['\"]?", attrs)
                    if name_match:
                        return page.get_by_role(role_name, name=name_match.group(1))  # type: ignore[arg-type]
                return page.get_by_role(role_name)  # type: ignore[arg-type]

            case "label":
                return page.get_by_label(value)

            case "placeholder":
                return page.get_by_placeholder(value)

            case "text":
                return page.get_by_text(value)

            case "testid":
                return page.get_by_test_id(value)

            case "xpath":
                return page.locator(f"xpath={value}")

            case "id":
                return page.locator(f"#{value}")

            case "css" | _:
                return page.locator(parsed.playwright_selector)

    except Exception as exc:
        raise SelectorError(
            parsed.playwright_selector,
            f"Failed to build locator: {exc}",
        ) from exc


async def resolve_and_wait(
    page: Page,
    parsed: ParsedSelector,
    *,
    timeout: int = 30_000,
    state: str = "visible",
) -> Locator:
    """
    Resolve a selector to a Locator and wait for the element to be in the
    desired state before returning.

    Args:
        page:    The Playwright Page.
        parsed:  ParsedSelector from parse_selector().
        timeout: Wait timeout in ms.
        state:   Element state to wait for: 'visible', 'attached', 'hidden', 'detached'.

    Returns:
        A Playwright Locator for the found element.

    Raises:
        SelectorError: If element is not found within timeout.
        TimeoutError:  If wait times out.
    """
    from camoufox_mcp.utils.errors import TimeoutError

    locator = resolve_locator(page, parsed)
    try:
        await locator.wait_for(state=state, timeout=timeout)  # type: ignore[arg-type]
    except Exception as exc:
        msg = str(exc).lower()
        if "timeout" in msg:
            raise TimeoutError(
                f"wait for selector '{parsed.playwright_selector}'",
                timeout,
            ) from exc
        raise SelectorError(
            parsed.playwright_selector,
            str(exc),
            timeout_ms=timeout,
        ) from exc

    return locator
