"""
ScreenshotService — handles browser_screenshot tool requests.

Supports:
    full_page   Capture the entire scrollable page
    viewport    Capture only the visible viewport
    element     Capture a specific element by selector

Screenshots are saved to the configured screenshot directory.
Returns a file path reference — not raw binary data.

Path safety: filenames are sanitised, output is always inside screenshot_dir.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from camoufox_mcp.browser.manager import BrowserManager
from camoufox_mcp.browser.selector import resolve_and_wait
from camoufox_mcp.security.validation import parse_selector
from camoufox_mcp.utils.errors import BrowserError, SecurityError
from camoufox_mcp.utils.logging import get_logger

logger = get_logger(__name__)

# Allowed image formats
_ALLOWED_FORMATS = frozenset({"png", "jpeg", "jpg"})

# Sanitise filename: allow alphanum, dash, underscore, dot only
_SAFE_FILENAME = re.compile(r"[^a-zA-Z0-9_\-.]")


def _safe_filename(name: str, ext: str) -> str:
    """Return a sanitised filename with timestamp + UUID suffix."""
    base = _SAFE_FILENAME.sub("_", name)[:64] if name else "screenshot"
    ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    return f"{base}_{ts}_{uid}.{ext}"


def _validate_format(fmt: str) -> str:
    fmt = fmt.lower().strip()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in _ALLOWED_FORMATS:
        raise SecurityError(
            f"Screenshot format '{fmt}' is not allowed. Use one of: {sorted(_ALLOWED_FORMATS)}"
        )
    return fmt


class ScreenshotService:
    """
    Service layer for screenshot operations.

    Args:
        browser: The shared BrowserManager instance.
    """

    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    @property
    def _screenshot_dir(self) -> Path:
        return self._browser._settings.screenshot_dir

    # ------------------------------------------------------------------ #
    # browser_screenshot
    # ------------------------------------------------------------------ #

    async def take(
        self,
        session_id: str,
        *,
        mode: str = "viewport",
        selector: str | None = None,
        filename: str | None = None,
        image_format: str = "png",
        quality: int | None = None,
    ) -> dict[str, Any]:
        """
        Take a screenshot of the current page.

        Args:
            session_id:   Target session.
            mode:         'full_page', 'viewport', or 'element'.
            selector:     Required when mode='element'. CSS/role/text/etc selector.
            filename:     Optional base filename (sanitised automatically).
            image_format: 'png' or 'jpeg' (default: 'png').
            quality:      JPEG quality 1–100 (ignored for PNG).

        Returns:
            Dict with success, session_id, path, filename, width, height.

        Raises:
            SecurityError: If format or mode is invalid.
            BrowserError:  If screenshot fails.
        """
        image_format = _validate_format(image_format)

        if mode not in ("full_page", "viewport", "element"):
            raise SecurityError(
                f"Screenshot mode '{mode}' is not valid. Use 'full_page', 'viewport', or 'element'."
            )
        if mode == "element" and not selector:
            raise SecurityError("mode='element' requires a selector to be specified.")

        session = self._browser.get_session(session_id)
        session.touch()

        # Ensure screenshot directory exists
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

        safe_name = _safe_filename(filename or f"{session_id}_{mode}", image_format)
        output_path = self._screenshot_dir / safe_name

        # Verify path stays inside screenshot_dir
        if not str(output_path.resolve()).startswith(str(self._screenshot_dir.resolve())):
            raise SecurityError("Screenshot path is outside the allowed directory.")

        _timeout = self._browser._settings.default_timeout
        page = await self._browser.get_active_page(session_id)

        screenshot_kwargs: dict[str, Any] = {
            "path": str(output_path),
            "type": image_format,
            "timeout": _timeout,
        }
        if image_format == "jpeg":
            screenshot_kwargs["quality"] = quality or self._browser._settings.screenshot_quality

        try:
            if mode == "element":
                assert selector is not None
                parsed = parse_selector(selector)
                locator = await resolve_and_wait(page, parsed, timeout=_timeout)
                await locator.screenshot(**screenshot_kwargs)
            elif mode == "full_page":
                screenshot_kwargs["full_page"] = True
                await page.screenshot(**screenshot_kwargs)
            else:  # viewport
                screenshot_kwargs["full_page"] = False
                await page.screenshot(**screenshot_kwargs)

        except (SecurityError, BrowserError):
            raise
        except Exception as exc:
            raise BrowserError(f"Screenshot failed (mode={mode}): {exc}") from exc

        logger.info(
            "Screenshot taken",
            extra={
                "session_id": session_id,
                "tool": "browser_screenshot",
                "mode": mode,
                "path": str(output_path),
            },
        )

        return {
            "success": True,
            "session_id": session_id,
            "path": str(output_path),
            "filename": safe_name,
            "mode": mode,
            "format": image_format,
            "message": f"Screenshot saved to '{output_path}'.",
        }
