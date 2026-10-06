"""
Unit tests for Phase 2 — profiles, navigation URL validation,
context helpers, and service layer (no browser launch required).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from camoufox_mcp.browser.context import _page_id, list_page_ids
from camoufox_mcp.browser.profiles import ProfileManager
from camoufox_mcp.tools.navigation import _validate_url
from camoufox_mcp.utils.errors import (
    SecurityError,
    SessionNotFoundError,
)

# --------------------------------------------------------------------------- #
# ProfileManager
# --------------------------------------------------------------------------- #


class TestProfileManager:
    def test_valid_names_accepted(self, tmp_path):
        pm = ProfileManager(tmp_path)
        for name in ("default", "research", "test-1", "MyProfile", "a" * 64):
            pm.validate_name(name)  # should not raise

    def test_empty_name_rejected(self, tmp_path):
        pm = ProfileManager(tmp_path)
        with pytest.raises(SecurityError):
            pm.validate_name("")

    def test_name_with_slash_rejected(self, tmp_path):
        pm = ProfileManager(tmp_path)
        with pytest.raises(SecurityError):
            pm.validate_name("../evil")

    def test_name_with_dot_rejected(self, tmp_path):
        pm = ProfileManager(tmp_path)
        with pytest.raises(SecurityError):
            pm.validate_name("bad.name")

    def test_name_too_long_rejected(self, tmp_path):
        pm = ProfileManager(tmp_path)
        with pytest.raises(SecurityError):
            pm.validate_name("a" * 65)

    def test_name_with_space_rejected(self, tmp_path):
        pm = ProfileManager(tmp_path)
        with pytest.raises(SecurityError):
            pm.validate_name("bad name")

    def test_profile_path_returns_absolute(self, tmp_path):
        pm = ProfileManager(tmp_path)
        path = pm.profile_path("default")
        assert path.is_absolute()
        assert path.parent == tmp_path

    def test_ensure_profile_creates_dir(self, tmp_path):
        pm = ProfileManager(tmp_path)
        path = pm.ensure_profile("research")
        assert path.exists()
        assert path.is_dir()

    def test_list_profiles_empty(self, tmp_path):
        pm = ProfileManager(tmp_path)
        assert pm.list_profiles() == []

    def test_list_profiles_after_create(self, tmp_path):
        pm = ProfileManager(tmp_path)
        pm.ensure_profile("alpha")
        pm.ensure_profile("beta")
        profiles = pm.list_profiles()
        assert "alpha" in profiles
        assert "beta" in profiles

    def test_profile_exists_false(self, tmp_path):
        pm = ProfileManager(tmp_path)
        assert pm.profile_exists("nope") is False

    def test_profile_exists_true(self, tmp_path):
        pm = ProfileManager(tmp_path)
        pm.ensure_profile("exists")
        assert pm.profile_exists("exists") is True

    def test_profile_exists_invalid_name_returns_false(self, tmp_path):
        pm = ProfileManager(tmp_path)
        assert pm.profile_exists("../bad") is False

    def test_delete_profile(self, tmp_path):
        pm = ProfileManager(tmp_path)
        pm.ensure_profile("to-delete")
        assert pm.profile_exists("to-delete") is True
        pm.delete_profile("to-delete")
        assert pm.profile_exists("to-delete") is False

    def test_delete_nonexistent_profile_no_error(self, tmp_path):
        pm = ProfileManager(tmp_path)
        pm.delete_profile("nope")  # should not raise

    def test_root_property(self, tmp_path):
        pm = ProfileManager(tmp_path)
        assert pm.root == tmp_path.resolve()

    def test_profile_root_missing_list_returns_empty(self, tmp_path):
        pm = ProfileManager(tmp_path / "nonexistent")
        assert pm.list_profiles() == []


# --------------------------------------------------------------------------- #
# URL validation
# --------------------------------------------------------------------------- #


class TestValidateUrl:
    def test_http_allowed(self):
        _validate_url("http://example.com")

    def test_https_allowed(self):
        _validate_url("https://example.com/path?q=1")

    def test_ftp_blocked(self):
        with pytest.raises(SecurityError, match="ftp"):
            _validate_url("ftp://example.com")

    def test_file_scheme_blocked(self):
        with pytest.raises(SecurityError):
            _validate_url("file:///etc/passwd")

    def test_javascript_scheme_blocked(self):
        with pytest.raises(SecurityError):
            _validate_url("javascript:alert(1)")

    def test_empty_string_blocked(self):
        with pytest.raises(SecurityError):
            _validate_url("")

    def test_no_host_blocked(self):
        with pytest.raises(SecurityError):
            _validate_url("https://")

    def test_localhost_allowed(self):
        _validate_url("http://localhost:8080")

    def test_ip_address_allowed(self):
        _validate_url("http://127.0.0.1:3000/path")


# --------------------------------------------------------------------------- #
# Context helpers — page_id is deterministic per page object
# --------------------------------------------------------------------------- #


class TestPageId:
    def test_page_id_is_string(self):
        mock_page = MagicMock()
        pid = _page_id(mock_page)
        assert isinstance(pid, str)
        assert pid.startswith("0x")

    def test_same_object_same_id(self):
        mock_page = MagicMock()
        assert _page_id(mock_page) == _page_id(mock_page)

    def test_different_objects_different_ids(self):
        p1 = MagicMock()
        p2 = MagicMock()
        assert _page_id(p1) != _page_id(p2)

    def test_list_page_ids(self):
        pages = [MagicMock(), MagicMock(), MagicMock()]
        mock_context = MagicMock()
        mock_context.pages = pages
        ids = list_page_ids(mock_context)
        assert len(ids) == 3
        assert len(set(ids)) == 3  # all unique


# --------------------------------------------------------------------------- #
# NavigationService (mock BrowserManager — no real browser)
# --------------------------------------------------------------------------- #


@pytest.fixture
def mock_browser(tmp_path):
    """A BrowserManager with a fake session and mocked page."""
    from unittest.mock import AsyncMock, MagicMock

    from camoufox_mcp.browser.manager import BrowserManager, _Session
    from camoufox_mcp.config import Settings

    settings = Settings(
        profile_dir=tmp_path / "profiles",
        download_dir=tmp_path / "downloads",
        screenshot_dir=tmp_path / "screenshots",
    )
    manager = BrowserManager(settings)

    # Inject a fake session
    mock_page = MagicMock()
    mock_page.url = "about:blank"
    mock_page.goto = AsyncMock(return_value=MagicMock(status=200))
    mock_page.title = AsyncMock(return_value="Test Page")
    mock_page.go_back = AsyncMock(return_value=None)
    mock_page.go_forward = AsyncMock(return_value=None)
    mock_page.reload = AsyncMock(return_value=None)

    mock_context = MagicMock()
    mock_context.pages = [mock_page]

    fake_session = MagicMock(spec=_Session)
    fake_session.session_id = "session_test"
    fake_session.context = mock_context
    fake_session.profile = "default"
    fake_session.headless = True
    fake_session.touch = MagicMock()
    fake_session.to_info = MagicMock(
        return_value=MagicMock(
            model_dump=lambda: {
                "session_id": "session_test",
                "status": "active",
                "profile": "default",
            }
        )
    )

    manager._sessions["session_test"] = fake_session
    manager._active_pages = {"session_test": mock_page}

    # Patch get_active_page to return our mock page
    async def _get_active_page(sid):
        return mock_page

    manager.get_active_page = _get_active_page

    return manager, mock_page


class TestNavigationService:
    @pytest.mark.asyncio
    async def test_open_valid_url(self, mock_browser):
        from camoufox_mcp.tools.navigation import NavigationService

        manager, page = mock_browser
        svc = NavigationService(manager)

        # patch navigate_to helper
        with patch("camoufox_mcp.tools.navigation.navigate_to", new_callable=AsyncMock) as mock_nav:
            mock_nav.return_value = {
                "url": "https://example.com",
                "title": "Example Domain",
                "status": 200,
            }
            result = await svc.open("session_test", "https://example.com")

        assert result["success"] is True
        assert result["url"] == "https://example.com"
        assert result["session_id"] == "session_test"

    @pytest.mark.asyncio
    async def test_open_blocked_url(self, mock_browser):
        from camoufox_mcp.tools.navigation import NavigationService

        manager, _ = mock_browser
        svc = NavigationService(manager)

        with pytest.raises(SecurityError):
            await svc.open("session_test", "file:///etc/passwd")

    @pytest.mark.asyncio
    async def test_open_unknown_session(self, mock_browser):
        from camoufox_mcp.tools.navigation import NavigationService

        manager, _ = mock_browser
        svc = NavigationService(manager)

        with pytest.raises(SessionNotFoundError):
            await svc.open("bad_session", "https://example.com")


# --------------------------------------------------------------------------- #
# TabService (mock context — no real browser)
# --------------------------------------------------------------------------- #


class TestTabService:
    @pytest.mark.asyncio
    async def test_get_tabs_returns_list(self, mock_browser):
        from camoufox_mcp.models.page import PageInfo, TabsInfo
        from camoufox_mcp.tools.tabs import TabService

        manager, _ = mock_browser
        svc = TabService(manager)

        with patch("camoufox_mcp.tools.tabs.list_tabs", new_callable=AsyncMock) as mock_lt:
            mock_lt.return_value = TabsInfo(
                session_id="session_test",
                tabs=[
                    PageInfo(
                        page_id="0x1",
                        session_id="session_test",
                        url="https://example.com",
                        title="Example",
                        is_active=True,
                    )
                ],
                active_tab_id="0x1",
            )
            result = await svc.get_tabs("session_test")

        assert result["success"] is True
        assert result["count"] == 1
        assert result["active_tab_id"] == "0x1"

    @pytest.mark.asyncio
    async def test_get_tabs_unknown_session(self, mock_browser):
        from camoufox_mcp.tools.tabs import TabService

        manager, _ = mock_browser
        svc = TabService(manager)

        with pytest.raises(SessionNotFoundError):
            await svc.get_tabs("nonexistent")


# --------------------------------------------------------------------------- #
# SessionService
# --------------------------------------------------------------------------- #


class TestSessionService:
    @pytest.mark.asyncio
    async def test_list_sessions(self, mock_browser):
        from camoufox_mcp.tools.sessions import SessionService

        manager, _ = mock_browser
        svc = SessionService(manager)
        result = await svc.list_sessions()

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["sessions"]) == 1

    @pytest.mark.asyncio
    async def test_get_session_info_not_found(self, mock_browser):
        from camoufox_mcp.tools.sessions import SessionService

        manager, _ = mock_browser
        svc = SessionService(manager)

        with pytest.raises(SessionNotFoundError):
            await svc.get_session_info("bad_id")
