"""
Unit tests for Phase 3 — selector validation, key validation, scroll validation,
permission checks, and interaction/wait services (no browser launch required).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from camoufox_mcp.security.permissions import (
    PermissionRegistry,
    PermissionSet,
    check_permission,
    check_url_permissions,
)
from camoufox_mcp.security.validation import (
    parse_selector,
    validate_key,
    validate_scroll,
    validate_text_input,
)
from camoufox_mcp.utils.errors import SecurityError, SelectorError

# --------------------------------------------------------------------------- #
# Selector parsing
# --------------------------------------------------------------------------- #


class TestParseSelector:
    def test_css_prefix(self):
        p = parse_selector("css=.my-class")
        assert p.selector_type == "css"
        assert p.value == ".my-class"
        assert p.playwright_selector == ".my-class"

    def test_xpath_prefix(self):
        p = parse_selector("xpath=//div[@id='x']")
        assert p.selector_type == "xpath"
        assert "xpath=" in p.playwright_selector

    def test_text_prefix(self):
        p = parse_selector("text=Submit")
        assert p.selector_type == "text"
        assert "Submit" in p.playwright_selector

    def test_role_prefix(self):
        p = parse_selector("role=button")
        assert p.selector_type == "role"
        assert p.value == "button"

    def test_label_prefix(self):
        p = parse_selector("label=Email address")
        assert p.selector_type == "label"

    def test_placeholder_prefix(self):
        p = parse_selector("placeholder=Search...")
        assert p.selector_type == "placeholder"

    def test_id_prefix(self):
        p = parse_selector("id=submit-btn")
        assert p.selector_type == "id"
        assert p.playwright_selector == "#submit-btn"

    def test_testid_prefix(self):
        p = parse_selector("testid=my-button")
        assert p.selector_type == "testid"

    def test_hash_shorthand(self):
        p = parse_selector("#main-nav")
        assert p.selector_type == "css"
        assert p.playwright_selector == "#main-nav"

    def test_dot_shorthand(self):
        p = parse_selector(".submit-btn")
        assert p.selector_type == "css"
        assert p.playwright_selector == ".submit-btn"

    def test_bare_css_fallback(self):
        p = parse_selector("button[type='submit']")
        assert p.selector_type == "css"

    def test_empty_selector_raises(self):
        with pytest.raises(SelectorError):
            parse_selector("")

    def test_too_long_selector_raises(self):
        with pytest.raises(SelectorError):
            parse_selector("css=" + "a" * 2000)

    def test_css_empty_value_raises(self):
        with pytest.raises(SelectorError):
            parse_selector("css=")

    def test_repr_contains_type(self):
        p = parse_selector("css=.btn")
        assert "css" in repr(p)


# --------------------------------------------------------------------------- #
# Text input validation
# --------------------------------------------------------------------------- #


class TestValidateTextInput:
    def test_normal_text_passes(self):
        result = validate_text_input("hello world")
        assert result == "hello world"

    def test_empty_raises(self):
        with pytest.raises(SecurityError):
            validate_text_input("")

    def test_too_long_raises(self):
        with pytest.raises(SecurityError):
            validate_text_input("a" * 10_001)

    def test_null_bytes_stripped(self):
        result = validate_text_input("hello\x00world")
        assert "\x00" not in result
        assert "hello" in result

    def test_unicode_text_passes(self):
        result = validate_text_input("こんにちは")
        assert result == "こんにちは"

    def test_non_string_raises(self):
        with pytest.raises(SecurityError):
            validate_text_input(12345)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Key validation
# --------------------------------------------------------------------------- #


class TestValidateKey:
    def test_single_char_passes(self):
        assert validate_key("a") == "a"
        assert validate_key("1") == "1"
        assert validate_key("!") == "!"

    def test_named_key_passes(self):
        for key in ("Enter", "Escape", "Tab", "ArrowDown", "F5", "Backspace"):
            assert validate_key(key) == key

    def test_modifier_combo_passes(self):
        assert validate_key("Control+a") == "Control+a"
        assert validate_key("Shift+Enter") == "Shift+Enter"
        assert validate_key("Meta+r") == "Meta+r"
        assert validate_key("Alt+F4") == "Alt+F4"

    def test_unknown_named_key_raises(self):
        with pytest.raises(SecurityError):
            validate_key("SuperUnknownKey")

    def test_empty_key_raises(self):
        with pytest.raises(SecurityError):
            validate_key("")

    def test_invalid_combo_raises(self):
        with pytest.raises(SecurityError):
            validate_key("Control+BadKey123")

    def test_space_key_passes(self):
        assert validate_key(" ") == " "

    def test_space_named_passes(self):
        assert validate_key("Space") == "Space"


# --------------------------------------------------------------------------- #
# Scroll validation
# --------------------------------------------------------------------------- #


class TestValidateScroll:
    def test_valid_values(self):
        xi, yi = validate_scroll(0, 500)
        assert xi == 0
        assert yi == 500

    def test_negative_values_allowed(self):
        xi, yi = validate_scroll(-100, -200)
        assert xi == -100
        assert yi == -200

    def test_floats_converted_to_int(self):
        xi, yi = validate_scroll(10.7, 200.3)
        assert xi == 10
        assert yi == 200

    def test_exceeds_max_raises(self):
        with pytest.raises(SecurityError):
            validate_scroll(0, 100_000)

    def test_non_numeric_raises(self):
        with pytest.raises(SecurityError):
            validate_scroll("up", 0)  # type: ignore[arg-type]

    def test_zero_zero_passes(self):
        xi, yi = validate_scroll(0, 0)
        assert xi == 0
        assert yi == 0


# --------------------------------------------------------------------------- #
# Permission checks
# --------------------------------------------------------------------------- #


class TestPermissions:
    def test_check_permission_allows(self):
        check_permission(True, "click")  # should not raise

    def test_check_permission_denies(self):
        with pytest.raises(SecurityError, match="click"):
            check_permission(False, "click")

    def test_registry_defaults_permissive(self):
        reg = PermissionRegistry()
        perms = reg.get_permissions("any-session")
        assert perms.allow_click is True
        assert perms.allow_type is True
        assert perms.allow_scroll is True

    def test_registry_custom_perms(self):
        reg = PermissionRegistry()
        custom = PermissionSet(allow_click=False)
        reg.set_permissions("s1", custom)
        perms = reg.get_permissions("s1")
        assert perms.allow_click is False

    def test_registry_remove(self):
        reg = PermissionRegistry()
        reg.set_permissions("s1", PermissionSet(allow_click=False))
        reg.remove("s1")
        perms = reg.get_permissions("s1")
        assert perms.allow_click is True  # back to default

    def test_check_url_no_restrictions(self):
        perms = PermissionSet()
        check_url_permissions("https://example.com", perms)  # should not raise

    def test_check_url_blocked_pattern(self):
        perms = PermissionSet(blocked_url_patterns=["evil\\.com"])
        with pytest.raises(SecurityError):
            check_url_permissions("https://evil.com/path", perms)

    def test_check_url_allowed_list(self):
        perms = PermissionSet(allowed_url_patterns=["example\\.com"])
        check_url_permissions("https://example.com", perms)  # OK
        with pytest.raises(SecurityError):
            check_url_permissions("https://other.com", perms)

    def test_registry_clear(self):
        reg = PermissionRegistry()
        reg.set_permissions("s1", PermissionSet(allow_click=False))
        reg.clear()
        assert reg.get_permissions("s1").allow_click is True


# --------------------------------------------------------------------------- #
# InteractionService (mocked browser — no real browser)
# --------------------------------------------------------------------------- #


@pytest.fixture
def mock_browser_for_interaction(tmp_path):
    """Minimal BrowserManager mock with a fake session and async page."""
    from camoufox_mcp.browser.manager import BrowserManager, _Session
    from camoufox_mcp.config import Settings

    settings = Settings(
        profile_dir=tmp_path / "profiles",
        download_dir=tmp_path / "downloads",
        screenshot_dir=tmp_path / "screenshots",
    )
    manager = BrowserManager(settings)

    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    mock_page.keyboard = MagicMock()
    mock_page.keyboard.press = AsyncMock()
    mock_page.mouse = MagicMock()
    mock_page.mouse.wheel = AsyncMock()

    mock_context = MagicMock()
    mock_context.pages = [mock_page]

    fake_session = MagicMock(spec=_Session)
    fake_session.session_id = "session_test"
    fake_session.context = mock_context
    fake_session.touch = MagicMock()

    manager._sessions["session_test"] = fake_session

    async def _get_active_page(sid):
        return mock_page

    manager.get_active_page = _get_active_page
    return manager, mock_page


class TestInteractionService:
    @pytest.mark.asyncio
    async def test_click_calls_locator(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.interaction import InteractionService

        manager, page = mock_browser_for_interaction
        svc = InteractionService(manager)

        mock_locator = AsyncMock()
        mock_locator.click = AsyncMock()

        with patch(
            "camoufox_mcp.tools.interaction.resolve_and_wait",
            new_callable=AsyncMock,
            return_value=mock_locator,
        ):
            result = await svc.click("session_test", "css=button")

        assert result["success"] is True
        mock_locator.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_type_validates_text(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.interaction import InteractionService

        manager, _ = mock_browser_for_interaction
        svc = InteractionService(manager)

        with pytest.raises(SecurityError):
            await svc.type_text("session_test", "css=input", "")

    @pytest.mark.asyncio
    async def test_type_calls_locator(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.interaction import InteractionService

        manager, _ = mock_browser_for_interaction
        svc = InteractionService(manager)

        mock_locator = AsyncMock()
        mock_locator.type = AsyncMock()

        with patch(
            "camoufox_mcp.tools.interaction.resolve_and_wait",
            new_callable=AsyncMock,
            return_value=mock_locator,
        ):
            result = await svc.type_text("session_test", "css=input", "hello")

        assert result["success"] is True
        assert result["chars_typed"] == 5

    @pytest.mark.asyncio
    async def test_press_validates_key(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.interaction import InteractionService

        manager, _ = mock_browser_for_interaction
        svc = InteractionService(manager)

        with pytest.raises(SecurityError):
            await svc.press("session_test", "InvalidKeyXYZ")

    @pytest.mark.asyncio
    async def test_press_calls_keyboard(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.interaction import InteractionService

        manager, page = mock_browser_for_interaction
        svc = InteractionService(manager)

        result = await svc.press("session_test", "Enter")
        assert result["success"] is True
        page.keyboard.press.assert_called_once_with("Enter")

    @pytest.mark.asyncio
    async def test_scroll_validates_delta(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.interaction import InteractionService

        manager, _ = mock_browser_for_interaction
        svc = InteractionService(manager)

        with pytest.raises(SecurityError):
            await svc.scroll("session_test", 0, 999_999)

    @pytest.mark.asyncio
    async def test_scroll_calls_mouse_wheel(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.interaction import InteractionService

        manager, page = mock_browser_for_interaction
        svc = InteractionService(manager)

        result = await svc.scroll("session_test", 0, 300)
        assert result["success"] is True
        page.mouse.wheel.assert_called_once_with(0, 300)

    @pytest.mark.asyncio
    async def test_click_blocked_by_permission(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.interaction import InteractionService

        manager, _ = mock_browser_for_interaction
        reg = PermissionRegistry()
        reg.set_permissions("session_test", PermissionSet(allow_click=False))
        svc = InteractionService(manager, permissions=reg)

        with pytest.raises(SecurityError, match="click"):
            await svc.click("session_test", "css=button")


# --------------------------------------------------------------------------- #
# WaitService
# --------------------------------------------------------------------------- #


class TestWaitService:
    @pytest.mark.asyncio
    async def test_wait_requires_one_target(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.wait import WaitService

        manager, _ = mock_browser_for_interaction
        svc = WaitService(manager)

        with pytest.raises(SecurityError, match="exactly one"):
            await svc.wait("session_test")

    @pytest.mark.asyncio
    async def test_wait_rejects_multiple_targets(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.wait import WaitService

        manager, _ = mock_browser_for_interaction
        svc = WaitService(manager)

        with pytest.raises(SecurityError, match="one wait target"):
            await svc.wait("session_test", selector="css=div", url="https://example.com")

    @pytest.mark.asyncio
    async def test_wait_fixed_timeout(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.wait import WaitService

        manager, page = mock_browser_for_interaction
        svc = WaitService(manager)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await svc.wait("session_test", timeout_ms=100)

        assert result["success"] is True
        assert "timeout_ms=100" in result["waited_for"]
        mock_sleep.assert_called_once_with(0.1)

    @pytest.mark.asyncio
    async def test_wait_fixed_timeout_exceeds_max(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.wait import WaitService

        manager, _ = mock_browser_for_interaction
        svc = WaitService(manager)

        with pytest.raises(SecurityError, match="30000"):
            await svc.wait("session_test", timeout_ms=60_000)

    @pytest.mark.asyncio
    async def test_wait_invalid_load_state(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.wait import WaitService

        manager, page = mock_browser_for_interaction
        svc = WaitService(manager)

        with pytest.raises(SecurityError, match="load_state"):
            await svc.wait("session_test", load_state="invalid_state")

    @pytest.mark.asyncio
    async def test_wait_load_state_valid(self, mock_browser_for_interaction):
        from camoufox_mcp.tools.wait import WaitService

        manager, page = mock_browser_for_interaction
        page.wait_for_load_state = AsyncMock()
        svc = WaitService(manager)

        result = await svc.wait("session_test", load_state="domcontentloaded")
        assert result["success"] is True
        page.wait_for_load_state.assert_called_once()
