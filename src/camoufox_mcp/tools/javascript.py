"""
JavaScriptService — handles browser_eval tool requests.

Executes JavaScript expressions in the browser context of the active page.

Security design:
    - JavaScript is executed inside the browser sandbox (Playwright page.evaluate).
    - It cannot access the MCP server filesystem, network, or process.
    - Expression length is capped to prevent abuse.
    - Execution is guarded by the permission layer (allow_javascript flag).
    - Results are serialised to JSON-safe types before returning.

This tool is intentionally separate from interaction tools to make the
elevated risk visible and auditable.
"""

from __future__ import annotations

import json
from typing import Any

from camoufox_mcp.browser.manager import BrowserManager
from camoufox_mcp.security.permissions import PermissionRegistry, check_permission
from camoufox_mcp.utils.errors import JavaScriptError, SecurityError
from camoufox_mcp.utils.logging import get_logger

logger = get_logger(__name__)

# Maximum expression length
MAX_EXPRESSION_LENGTH = 10_000

# Result size limit (characters of JSON-serialised result)
MAX_RESULT_LENGTH = 100_000


class JavaScriptService:
    """
    Service layer for JavaScript evaluation.

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

    async def evaluate(
        self,
        session_id: str,
        expression: str,
        *,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate a JavaScript expression in the active page context.

        The expression is passed to Playwright's page.evaluate() which runs
        it inside the browser sandbox. The result is JSON-serialised.

        Args:
            session_id: Target session.
            expression: JavaScript expression or function body to evaluate.
                        Examples:
                            "document.title"
                            "() => document.querySelectorAll('a').length"
                            "window.location.href"
            timeout:    Evaluation timeout in ms.

        Returns:
            Dict with success, session_id, result, result_type.

        Raises:
            SecurityError:    If JavaScript is not permitted or expression is invalid.
            JavaScriptError:  If evaluation fails in the browser.
        """
        perms = self._perms.get_permissions(session_id)
        check_permission(perms.allow_javascript, "javascript_eval")

        if not expression or not isinstance(expression, str):
            raise SecurityError("JavaScript expression must be a non-empty string.")

        expression = expression.strip()

        if len(expression) > MAX_EXPRESSION_LENGTH:
            raise SecurityError(
                f"JavaScript expression is too long ({len(expression)} chars, "
                f"max {MAX_EXPRESSION_LENGTH})."
            )

        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.default_timeout

        page = await self._browser.get_active_page(session_id)

        logger.info(
            "Evaluating JavaScript",
            extra={
                "session_id": session_id,
                "tool": "browser_eval",
                "expression_length": len(expression),
                "url": page.url,
            },
        )

        try:
            raw_result = await page.evaluate(expression, timeout=_timeout)
        except Exception as exc:
            raise JavaScriptError(expression, str(exc)) from exc

        # Serialise result to JSON-safe form
        try:
            serialised = json.dumps(raw_result, default=str, ensure_ascii=False)
        except Exception:
            serialised = str(raw_result)

        # Enforce result size limit
        if len(serialised) > MAX_RESULT_LENGTH:
            serialised = serialised[:MAX_RESULT_LENGTH]
            truncated = True
        else:
            truncated = False

        # Deserialise back so we return a proper Python object
        try:
            result_value = json.loads(serialised)
        except Exception:
            result_value = serialised

        result_type = type(raw_result).__name__

        logger.info(
            "JavaScript evaluated",
            extra={
                "session_id": session_id,
                "tool": "browser_eval",
                "result_type": result_type,
                "truncated": truncated,
            },
        )

        return {
            "success": True,
            "session_id": session_id,
            "result": result_value,
            "result_type": result_type,
            "truncated": truncated,
            "url": page.url,
        }
