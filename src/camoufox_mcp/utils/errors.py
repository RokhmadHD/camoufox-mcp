"""
Custom exception hierarchy for Camoufox MCP.

Design rules:
  - Every exception carries a human-readable ``message`` that is safe to
    return to an AI agent via MCP.
  - No internal tracebacks or raw Python errors are surfaced to callers
    unless explicitly requested.
  - Subclass appropriately so callers can catch at the right granularity.

Hierarchy:
    CamoufoxMCPError          (base)
    ├── BrowserError          browser launch / close / lifecycle
    ├── SessionError          session not found / limit exceeded
    ├── ToolError             generic tool execution failure
    │   ├── NavigationError   goto / back / forward / reload
    │   ├── SelectorError     element not found / ambiguous selector
    │   ├── TimeoutError      wait_for_* exceeded configured timeout
    │   └── JavaScriptError   browser_eval failures
    ├── SecurityError         disallowed action / path traversal / URL blocked
    ├── DownloadError         file download failures
    └── ConfigurationError    bad or missing configuration at startup
"""

from __future__ import annotations


class CamoufoxMCPError(Exception):
    """Base class for all Camoufox MCP errors."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}\n{self.details}"
        return self.message

    def to_dict(self) -> dict[str, str | None]:
        """Serialise for MCP error responses."""
        return {
            "error": type(self).__name__,
            "message": self.message,
            "details": self.details,
        }


# --------------------------------------------------------------------------- #
# Browser
# --------------------------------------------------------------------------- #


class BrowserError(CamoufoxMCPError):
    """Browser could not be launched, connected to, or shut down cleanly."""


# --------------------------------------------------------------------------- #
# Session
# --------------------------------------------------------------------------- #


class SessionError(CamoufoxMCPError):
    """Session management failure (not found, expired, limit exceeded, etc.)."""


class SessionNotFoundError(SessionError):
    """Raised when a session_id does not exist in the registry."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"Session '{session_id}' not found. It may have been closed or never created."
        )
        self.session_id = session_id


class SessionLimitError(SessionError):
    """Raised when the maximum number of concurrent sessions is exceeded."""

    def __init__(self, limit: int) -> None:
        super().__init__(
            f"Cannot create a new session: maximum concurrent sessions ({limit}) reached. "
            "Close an existing session first."
        )
        self.limit = limit


# --------------------------------------------------------------------------- #
# Tools (generic + specialised)
# --------------------------------------------------------------------------- #


class ToolError(CamoufoxMCPError):
    """Generic tool execution failure."""


class NavigationError(ToolError):
    """Page navigation failed (goto, back, forward, reload)."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"Navigation to '{url}' failed: {reason}")
        self.url = url
        self.reason = reason


class SelectorError(ToolError):
    """Element matching a selector could not be found or was ambiguous."""

    def __init__(self, selector: str, reason: str, *, timeout_ms: int | None = None) -> None:
        if timeout_ms is not None:
            msg = f"Unable to find element '{selector}': {reason} (timeout: {timeout_ms}ms)"
        else:
            msg = f"Unable to find element '{selector}': {reason}"
        super().__init__(msg)
        self.selector = selector
        self.reason = reason
        self.timeout_ms = timeout_ms


class TimeoutError(ToolError):
    """A wait operation exceeded its configured timeout."""

    def __init__(self, operation: str, timeout_ms: int) -> None:
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_ms}ms. "
            "Consider increasing the timeout or checking that the page loaded correctly."
        )
        self.operation = operation
        self.timeout_ms = timeout_ms


class JavaScriptError(ToolError):
    """JavaScript evaluation in the browser context failed."""

    def __init__(self, expression: str, reason: str) -> None:
        # Truncate long expressions in the error message
        snippet = expression[:120] + "..." if len(expression) > 120 else expression
        super().__init__(f"JavaScript evaluation failed for expression '{snippet}': {reason}")
        self.expression = expression
        self.reason = reason


# --------------------------------------------------------------------------- #
# Security
# --------------------------------------------------------------------------- #


class SecurityError(CamoufoxMCPError):
    """An operation was blocked by the security / permission layer."""


class PathTraversalError(SecurityError):
    """A path contained a traversal attempt (e.g. ../../etc/passwd)."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Path '{path}' was rejected: path traversal is not allowed.")
        self.path = path


class URLBlockedError(SecurityError):
    """A URL was blocked by the configured allow/deny policy."""

    def __init__(self, url: str, reason: str = "not permitted by policy") -> None:
        super().__init__(f"URL '{url}' is blocked: {reason}")
        self.url = url


# --------------------------------------------------------------------------- #
# Downloads
# --------------------------------------------------------------------------- #


class DownloadError(CamoufoxMCPError):
    """File download failed or was rejected."""


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


class ConfigurationError(CamoufoxMCPError):
    """Invalid or missing configuration detected at startup."""
