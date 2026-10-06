"""
Unit tests for Phase 1 — configuration, models, and error hierarchy.

These tests do NOT launch a browser. They validate the foundation layer only.
"""

from __future__ import annotations

import pytest

from camoufox_mcp import __version__
from camoufox_mcp.config import Settings
from camoufox_mcp.models.session import SessionStatus
from camoufox_mcp.models.tools import ToolResult
from camoufox_mcp.utils.errors import (
    BrowserError,
    CamoufoxMCPError,
    ConfigurationError,
    DownloadError,
    JavaScriptError,
    NavigationError,
    PathTraversalError,
    SecurityError,
    SelectorError,
    SessionLimitError,
    SessionNotFoundError,
    ToolError,
    URLBlockedError,
)

# --------------------------------------------------------------------------- #
# Version
# --------------------------------------------------------------------------- #


def test_version_is_string():
    assert isinstance(__version__, str)
    assert __version__ == "0.1.0"


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


def test_settings_defaults():
    s = Settings()
    assert s.headless is True
    assert s.max_sessions == 5
    assert s.log_level == "INFO"
    assert s.default_timeout == 30_000


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("CAMOUFOX_HEADLESS", "false")
    monkeypatch.setenv("CAMOUFOX_MAX_SESSIONS", "10")
    monkeypatch.setenv("CAMOUFOX_LOG_LEVEL", "DEBUG")
    s = Settings()
    assert s.headless is False
    assert s.max_sessions == 10
    assert s.log_level == "DEBUG"


def test_settings_path_is_absolute():
    s = Settings()
    assert s.profile_dir.is_absolute()
    assert s.download_dir.is_absolute()
    assert s.screenshot_dir.is_absolute()


# --------------------------------------------------------------------------- #
# Error hierarchy
# --------------------------------------------------------------------------- #


def test_base_error_is_exception():
    err = CamoufoxMCPError("test message")
    assert isinstance(err, Exception)
    assert err.message == "test message"
    assert str(err) == "test message"


def test_base_error_with_details():
    err = CamoufoxMCPError("test", details="more info")
    assert "more info" in str(err)


def test_base_error_to_dict():
    err = CamoufoxMCPError("test", details="detail")
    d = err.to_dict()
    assert d["error"] == "CamoufoxMCPError"
    assert d["message"] == "test"
    assert d["details"] == "detail"


def test_session_not_found_error():
    err = SessionNotFoundError("abc123")
    assert isinstance(err, CamoufoxMCPError)
    assert "abc123" in err.message
    assert err.session_id == "abc123"


def test_session_limit_error():
    err = SessionLimitError(5)
    assert isinstance(err, CamoufoxMCPError)
    assert "5" in err.message
    assert err.limit == 5


def test_navigation_error():
    err = NavigationError("https://example.com", "connection refused")
    assert isinstance(err, ToolError)
    assert "https://example.com" in err.message
    assert "connection refused" in err.message


def test_selector_error_with_timeout():
    err = SelectorError("button.submit", "not found", timeout_ms=5000)
    assert isinstance(err, ToolError)
    assert "button.submit" in err.message
    assert "5000" in err.message


def test_selector_error_without_timeout():
    err = SelectorError("input#email", "ambiguous")
    assert "input#email" in err.message
    assert err.timeout_ms is None


def test_javascript_error_truncates_long_expression():
    long_expr = "x" * 200
    err = JavaScriptError(long_expr, "syntax error")
    assert len(err.message) < len(long_expr) + 100  # truncated
    assert "..." in err.message


def test_path_traversal_error():
    err = PathTraversalError("../../etc/passwd")
    assert isinstance(err, SecurityError)
    assert "../../etc/passwd" in err.message


def test_url_blocked_error():
    err = URLBlockedError("https://blocked.com")
    assert isinstance(err, SecurityError)
    assert "https://blocked.com" in err.message


def test_error_inheritance():
    assert issubclass(BrowserError, CamoufoxMCPError)
    assert issubclass(SessionNotFoundError, CamoufoxMCPError)
    assert issubclass(ToolError, CamoufoxMCPError)
    assert issubclass(NavigationError, ToolError)
    assert issubclass(SelectorError, ToolError)
    assert issubclass(JavaScriptError, ToolError)
    assert issubclass(SecurityError, CamoufoxMCPError)
    assert issubclass(PathTraversalError, SecurityError)
    assert issubclass(URLBlockedError, SecurityError)
    assert issubclass(DownloadError, CamoufoxMCPError)
    assert issubclass(ConfigurationError, CamoufoxMCPError)


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


def test_session_status_values():
    assert SessionStatus.ACTIVE == "active"
    assert SessionStatus.CLOSED == "closed"
    assert SessionStatus.ERROR == "error"


def test_tool_result_ok():
    r = ToolResult.ok("done", url="https://example.com", title="Example")
    assert r.success is True
    assert r.message == "done"
    assert r.data is not None
    assert r.data["url"] == "https://example.com"
    assert r.error is None


def test_tool_result_ok_no_data():
    r = ToolResult.ok()
    assert r.success is True
    assert r.data is None


def test_tool_result_fail():
    r = ToolResult.fail("SelectorError", "could not find element")
    assert r.success is False
    assert r.error == "SelectorError"
    assert r.message == "could not find element"


# --------------------------------------------------------------------------- #
# BrowserManager (no-browser unit tests)
# --------------------------------------------------------------------------- #


def test_browser_manager_initial_state():
    from camoufox_mcp.browser.manager import BrowserManager

    settings = Settings()
    manager = BrowserManager(settings)
    assert manager.session_count() == 0
    assert manager.is_started() is False


def test_browser_manager_get_session_raises_not_found():
    from camoufox_mcp.browser.manager import BrowserManager

    settings = Settings()
    manager = BrowserManager(settings)
    with pytest.raises(SessionNotFoundError):
        manager.get_session("nonexistent")


@pytest.mark.asyncio
async def test_browser_manager_start_creates_dirs(tmp_path):
    from camoufox_mcp.browser.manager import BrowserManager

    settings = Settings(
        profile_dir=tmp_path / "profiles",
        download_dir=tmp_path / "downloads",
        screenshot_dir=tmp_path / "screenshots",
    )
    manager = BrowserManager(settings)
    await manager.start()
    assert manager.is_started() is True
    assert (tmp_path / "profiles").exists()
    assert (tmp_path / "downloads").exists()
    assert (tmp_path / "screenshots").exists()


@pytest.mark.asyncio
async def test_browser_manager_start_idempotent(tmp_path):
    from camoufox_mcp.browser.manager import BrowserManager

    settings = Settings(
        profile_dir=tmp_path / "profiles",
        download_dir=tmp_path / "downloads",
        screenshot_dir=tmp_path / "screenshots",
    )
    manager = BrowserManager(settings)
    await manager.start()
    await manager.start()  # second call must be a no-op
    assert manager.is_started() is True


@pytest.mark.asyncio
async def test_browser_manager_session_limit(tmp_path, monkeypatch):
    """Verify SessionLimitError is raised when limit is exceeded."""
    from camoufox_mcp.browser.manager import BrowserManager

    settings = Settings(
        max_sessions=2,
        profile_dir=tmp_path / "profiles",
        download_dir=tmp_path / "downloads",
        screenshot_dir=tmp_path / "screenshots",
    )
    manager = BrowserManager(settings)
    manager._started = True

    # Manually inject fake sessions to simulate full capacity
    from unittest.mock import MagicMock

    from camoufox_mcp.browser.manager import _Session

    for i in range(2):
        fake = MagicMock(spec=_Session)
        manager._sessions[f"session_fake_{i}"] = fake

    with pytest.raises(SessionLimitError):
        await manager.create_session()
