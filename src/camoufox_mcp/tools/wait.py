"""
WaitService — handles all browser_wait tool requests.

Supports:
    wait_for_selector   Wait until an element appears/disappears
    wait_for_url        Wait until page URL matches a pattern
    wait_for_load_state Wait until the page reaches a load state
    wait_for_timeout    Wait a fixed number of milliseconds (avoid unless necessary)

Design principle:
    Deterministic waits (selector/url/load_state) are preferred.
    Fixed-time sleeps (timeout) are allowed but flagged in log.

Tool flow:
    browser_wait
        ↓
    WaitService
        ↓
    BrowserManager (get_active_page)
        ↓
    Playwright Page wait_for_* methods
"""

from __future__ import annotations

from typing import Any

from camoufox_mcp.browser.manager import BrowserManager
from camoufox_mcp.browser.selector import resolve_and_wait
from camoufox_mcp.security.permissions import PermissionRegistry, check_permission
from camoufox_mcp.security.validation import parse_selector
from camoufox_mcp.utils.errors import TimeoutError
from camoufox_mcp.utils.logging import get_logger

logger = get_logger(__name__)

# Valid Playwright load states
_LOAD_STATES = frozenset({"domcontentloaded", "load", "networkidle"})

# Maximum allowed fixed-sleep in ms (prevent abuse)
MAX_FIXED_TIMEOUT_MS = 30_000


class WaitService:
    """
    Service layer for browser wait operations.

    Args:
        browser:     The shared BrowserManager instance.
        permissions: Optional PermissionRegistry.
    """

    def __init__(
        self,
        browser: BrowserManager,
        permissions: PermissionRegistry | None = None,
    ) -> None:
        self._browser = browser
        self._perms = permissions or PermissionRegistry()

    # ------------------------------------------------------------------ #
    # browser_wait (unified entry point)
    # ------------------------------------------------------------------ #

    async def wait(
        self,
        session_id: str,
        *,
        selector: str | None = None,
        url: str | None = None,
        load_state: str | None = None,
        timeout_ms: int | None = None,
        timeout: int | None = None,
        state: str = "visible",
    ) -> dict[str, Any]:
        """
        Unified wait dispatcher — exactly one of the wait parameters must be set.

        Args:
            session_id: Target session.
            selector:   Wait until this element is in the given state.
            url:        Wait until page URL contains this string or matches regex.
            load_state: Wait for 'domcontentloaded', 'load', or 'networkidle'.
            timeout_ms: Fixed sleep in ms (use only as last resort).
            timeout:    Maximum wait time in ms (applies to all wait types).
            state:      Element state for selector wait ('visible', 'attached', etc.)

        Returns:
            Dict with success, session_id, waited_for, duration_ms.

        Raises:
            SecurityError:  If wait is not permitted.
            TimeoutError:   If wait times out.
            ValueError:     If none or multiple wait targets specified.
        """
        from camoufox_mcp.utils.errors import SecurityError

        perms = self._perms.get_permissions(session_id)
        check_permission(perms.allow_wait, "wait")

        # Exactly one wait target must be set
        targets = [t for t in (selector, url, load_state, timeout_ms) if t is not None]
        if len(targets) == 0:
            raise SecurityError(
                "browser_wait requires exactly one of: selector, url, load_state, timeout_ms"
            )
        if len(targets) > 1:
            raise SecurityError(
                "browser_wait accepts only one wait target at a time. "
                "Specify exactly one of: selector, url, load_state, timeout_ms"
            )

        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.default_timeout

        page = await self._browser.get_active_page(session_id)

        import time

        start = time.monotonic()

        if selector is not None:
            await self._wait_for_selector(page, selector, state=state, timeout=_timeout)
            waited_for = f"selector='{selector}' state='{state}'"

        elif url is not None:
            await self._wait_for_url(page, url, timeout=_timeout)
            waited_for = f"url='{url}'"

        elif load_state is not None:
            await self._wait_for_load_state(page, load_state, timeout=_timeout)
            waited_for = f"load_state='{load_state}'"

        else:  # timeout_ms
            ms = int(timeout_ms)  # type: ignore[arg-type]
            if ms > MAX_FIXED_TIMEOUT_MS:
                raise SecurityError(
                    f"Fixed timeout {ms}ms exceeds maximum allowed ({MAX_FIXED_TIMEOUT_MS}ms). "
                    "Use a deterministic wait instead."
                )
            logger.warning(
                "Using fixed sleep — prefer deterministic waits",
                extra={"session_id": session_id, "timeout_ms": ms},
            )
            import asyncio

            await asyncio.sleep(ms / 1000)
            waited_for = f"timeout_ms={ms}"

        duration_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "Wait complete",
            extra={
                "session_id": session_id,
                "tool": "browser_wait",
                "waited_for": waited_for,
                "duration_ms": duration_ms,
            },
        )
        return {
            "success": True,
            "session_id": session_id,
            "waited_for": waited_for,
            "duration_ms": duration_ms,
            "url": page.url,
        }

    # ------------------------------------------------------------------ #
    # Private wait helpers
    # ------------------------------------------------------------------ #

    async def _wait_for_selector(
        self,
        page: Any,
        selector: str,
        *,
        state: str = "visible",
        timeout: int,
    ) -> None:
        parsed = parse_selector(selector)
        await resolve_and_wait(page, parsed, timeout=timeout, state=state)

    async def _wait_for_url(
        self,
        page: Any,
        url_pattern: str,
        *,
        timeout: int,
    ) -> None:
        try:
            await page.wait_for_url(url_pattern, timeout=timeout)
        except Exception as exc:
            if "timeout" in str(exc).lower():
                raise TimeoutError(f"wait_for_url '{url_pattern}'", timeout) from exc
            raise

    async def _wait_for_load_state(
        self,
        page: Any,
        state: str,
        *,
        timeout: int,
    ) -> None:
        if state not in _LOAD_STATES:
            from camoufox_mcp.utils.errors import SecurityError

            raise SecurityError(
                f"Invalid load_state '{state}'. Allowed values: {sorted(_LOAD_STATES)}"
            )
        try:
            await page.wait_for_load_state(state, timeout=timeout)
        except Exception as exc:
            if "timeout" in str(exc).lower():
                raise TimeoutError(f"wait_for_load_state '{state}'", timeout) from exc
            raise
