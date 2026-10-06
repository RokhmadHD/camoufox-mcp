"""
InteractionService — handles click, type, press, and scroll tool requests.

Tool flow:
    browser_click / browser_type / browser_press / browser_scroll
        ↓
    InteractionService
        ↓
    security/validation.py   (validate selector, text, key, scroll)
    security/permissions.py  (check permission flags)
        ↓
    browser/selector.py      (resolve to Playwright Locator)
        ↓
    Playwright Page / Locator
"""

from __future__ import annotations

from typing import Any

from camoufox_mcp.browser.manager import BrowserManager
from camoufox_mcp.browser.selector import resolve_and_wait
from camoufox_mcp.security.permissions import PermissionRegistry, check_permission
from camoufox_mcp.security.validation import (
    parse_selector,
    validate_key,
    validate_scroll,
    validate_text_input,
)
from camoufox_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class InteractionService:
    """
    Service layer for user interaction operations.

    Args:
        browser:    The shared BrowserManager instance.
        permissions: Optional PermissionRegistry. Defaults to permissive.
    """

    def __init__(
        self,
        browser: BrowserManager,
        permissions: PermissionRegistry | None = None,
    ) -> None:
        self._browser = browser
        self._perms = permissions or PermissionRegistry()

    # ------------------------------------------------------------------ #
    # browser_click
    # ------------------------------------------------------------------ #

    async def click(
        self,
        session_id: str,
        selector: str,
        *,
        timeout: int | None = None,
        button: str = "left",
        click_count: int = 1,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Click an element matching the selector.

        Args:
            session_id:  Target session.
            selector:    Element selector string (css=, xpath=, role=, text=, etc.).
            timeout:     Wait timeout (ms) before clicking.
            button:      Mouse button: 'left', 'right', 'middle'.
            click_count: Number of clicks (2 = double-click).
            force:       Skip actionability checks if True.

        Returns:
            Dict with success, session_id, selector, url.

        Raises:
            SecurityError:  If click is not permitted.
            SelectorError:  If the element cannot be found.
            TimeoutError:   If the wait times out.
        """
        perms = self._perms.get_permissions(session_id)
        check_permission(perms.allow_click, "click")

        parsed = parse_selector(selector)
        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.default_timeout

        page = await self._browser.get_active_page(session_id)
        locator = await resolve_and_wait(page, parsed, timeout=_timeout)

        if button not in ("left", "right", "middle"):
            button = "left"
        if click_count not in (1, 2, 3):
            click_count = 1

        await locator.click(
            button=button,  # type: ignore[arg-type]
            click_count=click_count,
            force=force,
            timeout=_timeout,
        )

        logger.info(
            "Clicked element",
            extra={
                "session_id": session_id,
                "tool": "browser_click",
                "selector": selector,
                "url": page.url,
            },
        )
        return {
            "success": True,
            "session_id": session_id,
            "selector": selector,
            "url": page.url,
            "message": f"Clicked element '{selector}'.",
        }

    # ------------------------------------------------------------------ #
    # browser_type
    # ------------------------------------------------------------------ #

    async def type_text(
        self,
        session_id: str,
        selector: str,
        text: str,
        *,
        timeout: int | None = None,
        delay: int = 0,
        clear_first: bool = False,
    ) -> dict[str, Any]:
        """
        Type text into an element matching the selector.

        Args:
            session_id: Target session.
            selector:   Element selector string.
            text:       Text to type.
            timeout:    Wait timeout (ms).
            delay:      Delay between keystrokes in ms (0 = instant).
            clear_first: If True, clear the field before typing.

        Returns:
            Dict with success, session_id, selector, chars_typed.

        Raises:
            SecurityError: If type is not permitted or text is invalid.
            SelectorError: If element is not found.
        """
        perms = self._perms.get_permissions(session_id)
        check_permission(perms.allow_type, "type")

        text = validate_text_input(text)
        parsed = parse_selector(selector)
        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.default_timeout

        page = await self._browser.get_active_page(session_id)
        locator = await resolve_and_wait(page, parsed, timeout=_timeout)

        if clear_first:
            await locator.clear(timeout=_timeout)

        await locator.type(text, delay=delay, timeout=_timeout)

        logger.info(
            "Typed text",
            extra={
                "session_id": session_id,
                "tool": "browser_type",
                "selector": selector,
                "chars": len(text),
            },
        )
        return {
            "success": True,
            "session_id": session_id,
            "selector": selector,
            "chars_typed": len(text),
            "message": f"Typed {len(text)} characters into '{selector}'.",
        }

    # ------------------------------------------------------------------ #
    # browser_press
    # ------------------------------------------------------------------ #

    async def press(
        self,
        session_id: str,
        key: str,
        selector: str | None = None,
        *,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Press a keyboard key, optionally focused on an element.

        Args:
            session_id: Target session.
            key:        Key name (e.g. 'Enter', 'Escape', 'Control+a').
            selector:   Optional element selector to focus before pressing.
            timeout:    Wait timeout (ms) for element resolution.

        Returns:
            Dict with success, session_id, key.

        Raises:
            SecurityError: If key press is not permitted or key is invalid.
            SelectorError: If selector provided but element not found.
        """
        perms = self._perms.get_permissions(session_id)
        check_permission(perms.allow_key_press, "key_press")

        key = validate_key(key)
        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.default_timeout

        page = await self._browser.get_active_page(session_id)

        if selector:
            parsed = parse_selector(selector)
            locator = await resolve_and_wait(page, parsed, timeout=_timeout)
            await locator.press(key, timeout=_timeout)
        else:
            await page.keyboard.press(key)

        logger.info(
            "Pressed key",
            extra={
                "session_id": session_id,
                "tool": "browser_press",
                "key": key,
                "selector": selector,
            },
        )
        return {
            "success": True,
            "session_id": session_id,
            "key": key,
            "selector": selector,
            "message": f"Pressed key '{key}'" + (f" on '{selector}'" if selector else "") + ".",
        }

    # ------------------------------------------------------------------ #
    # browser_scroll
    # ------------------------------------------------------------------ #

    async def scroll(
        self,
        session_id: str,
        x: int = 0,
        y: int = 500,
        *,
        selector: str | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Scroll the page or a specific element.

        Args:
            session_id: Target session.
            x:          Horizontal scroll delta in pixels.
            y:          Vertical scroll delta in pixels (positive = down).
            selector:   Optional element to scroll within (scrolls page if None).
            timeout:    Wait timeout (ms) for element resolution.

        Returns:
            Dict with success, session_id, x, y.

        Raises:
            SecurityError: If scroll is not permitted or deltas are invalid.
        """
        perms = self._perms.get_permissions(session_id)
        check_permission(perms.allow_scroll, "scroll")

        xi, yi = validate_scroll(x, y)
        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.default_timeout

        page = await self._browser.get_active_page(session_id)

        if selector:
            parsed = parse_selector(selector)
            locator = await resolve_and_wait(page, parsed, timeout=_timeout)
            await locator.evaluate(
                "([el, x, y]) => el.scrollBy(x, y)",
                [None, xi, yi],
            )
        else:
            await page.mouse.wheel(xi, yi)

        logger.info(
            "Scrolled",
            extra={
                "session_id": session_id,
                "tool": "browser_scroll",
                "x": xi,
                "y": yi,
                "selector": selector,
            },
        )
        return {
            "success": True,
            "session_id": session_id,
            "x": xi,
            "y": yi,
            "selector": selector,
            "message": f"Scrolled ({xi}, {yi})"
            + (f" within '{selector}'" if selector else "")
            + ".",
        }
