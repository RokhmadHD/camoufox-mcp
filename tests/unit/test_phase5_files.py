"""
Unit tests for Phase 5 — screenshot, downloads, and JavaScript eval.
No real browser required — all browser interactions are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_session_manager(tmp_path):
    """Return a BrowserManager with one fake session and a mock page."""
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
    mock_page.screenshot = AsyncMock(return_value=None)
    mock_page.evaluate = AsyncMock(return_value="test result")
    mock_page.goto = AsyncMock(return_value=MagicMock(status=200))

    fake_session = MagicMock(spec=_Session)
    fake_session.session_id = "s1"
    fake_session.touch = MagicMock()
    manager._sessions["s1"] = fake_session

    async def _get_page(_):
        return mock_page

    manager.get_active_page = _get_page
    return manager, mock_page, settings


# --------------------------------------------------------------------------- #
# _sanitise_filename (downloads)
# --------------------------------------------------------------------------- #


class TestSanitiseFilename:
    def test_normal_name(self):
        from camoufox_mcp.tools.downloads import _sanitise_filename

        assert _sanitise_filename("report.pdf") == "report.pdf"

    def test_strips_dangerous_chars(self):
        from camoufox_mcp.tools.downloads import _sanitise_filename

        result = _sanitise_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_empty_name_becomes_download(self):
        from camoufox_mcp.tools.downloads import _sanitise_filename

        assert _sanitise_filename("") == "download"
        assert _sanitise_filename("   ") == "download"

    def test_null_bytes_removed(self):
        from camoufox_mcp.tools.downloads import _sanitise_filename

        result = _sanitise_filename("file\x00name.txt")
        assert "\x00" not in result

    def test_long_name_truncated(self):
        from camoufox_mcp.tools.downloads import _sanitise_filename

        long = "a" * 500
        result = _sanitise_filename(long)
        assert len(result) <= 255


# --------------------------------------------------------------------------- #
# _validate_download_path
# --------------------------------------------------------------------------- #


class TestValidateDownloadPath:
    def test_valid_path_inside_dir(self, tmp_path):
        from camoufox_mcp.tools.downloads import _validate_download_path

        dl_dir = tmp_path / "downloads"
        dl_dir.mkdir()
        _validate_download_path(dl_dir / "file.pdf", dl_dir)  # should not raise

    def test_traversal_rejected(self, tmp_path):
        from camoufox_mcp.tools.downloads import _validate_download_path
        from camoufox_mcp.utils.errors import PathTraversalError

        dl_dir = tmp_path / "downloads"
        dl_dir.mkdir()
        evil = dl_dir / ".." / "secret.txt"
        with pytest.raises(PathTraversalError):
            _validate_download_path(evil, dl_dir)


# --------------------------------------------------------------------------- #
# Screenshot — _validate_format, _safe_filename
# --------------------------------------------------------------------------- #


class TestScreenshotHelpers:
    def test_valid_formats(self):
        from camoufox_mcp.tools.screenshot import _validate_format

        assert _validate_format("png") == "png"
        assert _validate_format("jpeg") == "jpeg"
        assert _validate_format("jpg") == "jpeg"  # normalised

    def test_invalid_format_raises(self):
        from camoufox_mcp.tools.screenshot import _validate_format
        from camoufox_mcp.utils.errors import SecurityError

        with pytest.raises(SecurityError):
            _validate_format("gif")

    def test_case_insensitive(self):
        from camoufox_mcp.tools.screenshot import _validate_format

        assert _validate_format("PNG") == "png"
        assert _validate_format("JPEG") == "jpeg"

    def test_safe_filename_contains_ext(self):
        from camoufox_mcp.tools.screenshot import _safe_filename

        name = _safe_filename("test", "png")
        assert name.endswith(".png")

    def test_safe_filename_has_uuid(self):
        from camoufox_mcp.tools.screenshot import _safe_filename

        n1 = _safe_filename("test", "png")
        n2 = _safe_filename("test", "png")
        assert n1 != n2  # unique due to UUID suffix

    def test_safe_filename_sanitises_special_chars(self):
        from camoufox_mcp.tools.screenshot import _safe_filename

        name = _safe_filename("my file/with:bad chars", "png")
        assert "/" not in name
        assert ":" not in name


# --------------------------------------------------------------------------- #
# ScreenshotService
# --------------------------------------------------------------------------- #


class TestScreenshotService:
    @pytest.mark.asyncio
    async def test_viewport_screenshot(self, tmp_path):
        from camoufox_mcp.tools.screenshot import ScreenshotService

        manager, page, settings = _make_session_manager(tmp_path)
        settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
        svc = ScreenshotService(manager)

        with patch("camoufox_mcp.tools.screenshot.resolve_and_wait"):
            result = await svc.take("s1", mode="viewport")

        assert result["success"] is True
        assert result["mode"] == "viewport"
        assert result["format"] == "png"
        page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_page_screenshot(self, tmp_path):
        from camoufox_mcp.tools.screenshot import ScreenshotService

        manager, page, settings = _make_session_manager(tmp_path)
        settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
        svc = ScreenshotService(manager)

        result = await svc.take("s1", mode="full_page")

        assert result["success"] is True
        call_kwargs = page.screenshot.call_args[1]
        assert call_kwargs["full_page"] is True

    @pytest.mark.asyncio
    async def test_element_mode_requires_selector(self, tmp_path):
        from camoufox_mcp.tools.screenshot import ScreenshotService
        from camoufox_mcp.utils.errors import SecurityError

        manager, _, settings = _make_session_manager(tmp_path)
        svc = ScreenshotService(manager)

        with pytest.raises(SecurityError, match="selector"):
            await svc.take("s1", mode="element")

    @pytest.mark.asyncio
    async def test_invalid_mode_raises(self, tmp_path):
        from camoufox_mcp.tools.screenshot import ScreenshotService
        from camoufox_mcp.utils.errors import SecurityError

        manager, _, settings = _make_session_manager(tmp_path)
        svc = ScreenshotService(manager)

        with pytest.raises(SecurityError, match="mode"):
            await svc.take("s1", mode="panorama")

    @pytest.mark.asyncio
    async def test_invalid_format_raises(self, tmp_path):
        from camoufox_mcp.tools.screenshot import ScreenshotService
        from camoufox_mcp.utils.errors import SecurityError

        manager, _, settings = _make_session_manager(tmp_path)
        svc = ScreenshotService(manager)

        with pytest.raises(SecurityError):
            await svc.take("s1", mode="viewport", image_format="bmp")


# --------------------------------------------------------------------------- #
# DownloadService
# --------------------------------------------------------------------------- #


class TestDownloadService:
    @pytest.mark.asyncio
    async def test_list_downloads_empty(self, tmp_path):
        from camoufox_mcp.tools.downloads import DownloadService

        manager, _, _ = _make_session_manager(tmp_path)
        svc = DownloadService(manager)
        result = await svc.list_downloads()

        assert result["success"] is True
        assert result["count"] == 0
        assert result["files"] == []

    @pytest.mark.asyncio
    async def test_list_downloads_with_files(self, tmp_path):
        from camoufox_mcp.tools.downloads import DownloadService

        manager, _, settings = _make_session_manager(tmp_path)
        settings.download_dir.mkdir(parents=True, exist_ok=True)
        (settings.download_dir / "report.pdf").write_bytes(b"data")
        (settings.download_dir / "data.csv").write_bytes(b"a,b,c")

        svc = DownloadService(manager)
        result = await svc.list_downloads()

        assert result["count"] == 2
        filenames = [f["filename"] for f in result["files"]]
        assert "report.pdf" in filenames
        assert "data.csv" in filenames

    @pytest.mark.asyncio
    async def test_clear_downloads(self, tmp_path):
        from camoufox_mcp.tools.downloads import DownloadService

        manager, _, settings = _make_session_manager(tmp_path)
        settings.download_dir.mkdir(parents=True, exist_ok=True)
        (settings.download_dir / "file1.txt").write_bytes(b"x")
        (settings.download_dir / "file2.txt").write_bytes(b"y")

        svc = DownloadService(manager)
        result = await svc.clear_downloads()

        assert result["success"] is True
        assert result["deleted_count"] == 2
        assert list(settings.download_dir.iterdir()) == []

    @pytest.mark.asyncio
    async def test_clear_nonexistent_dir(self, tmp_path):
        from camoufox_mcp.tools.downloads import DownloadService

        manager, _, _ = _make_session_manager(tmp_path)
        svc = DownloadService(manager)
        # download_dir doesn't exist yet
        result = await svc.clear_downloads()

        assert result["success"] is True
        assert result["deleted_count"] == 0

    @pytest.mark.asyncio
    async def test_start_download_blocks_traversal(self, tmp_path):

        manager, _, settings = _make_session_manager(tmp_path)
        settings.download_dir.mkdir(parents=True, exist_ok=True)

        # filename with traversal — should be sanitised, not cause traversal
        # the sanitiser strips .., so this should be safe
        result_filename = __import__(
            "camoufox_mcp.tools.downloads", fromlist=["_sanitise_filename"]
        )._sanitise_filename("../../evil.sh")
        assert ".." not in result_filename

    @pytest.mark.asyncio
    async def test_start_download_rejects_bad_url(self, tmp_path):
        from camoufox_mcp.tools.downloads import DownloadService
        from camoufox_mcp.utils.errors import SecurityError

        manager, _, _ = _make_session_manager(tmp_path)
        svc = DownloadService(manager)

        with pytest.raises(SecurityError):
            await svc.start_download("s1", "ftp://evil.com/file.sh")


# --------------------------------------------------------------------------- #
# JavaScriptService
# --------------------------------------------------------------------------- #


class TestJavaScriptService:
    @pytest.mark.asyncio
    async def test_basic_eval(self, tmp_path):
        from camoufox_mcp.tools.javascript import JavaScriptService

        manager, page, _ = _make_session_manager(tmp_path)
        page.evaluate = AsyncMock(return_value="Example Domain")
        svc = JavaScriptService(manager)

        result = await svc.evaluate("s1", "document.title")

        assert result["success"] is True
        assert result["result"] == "Example Domain"
        assert result["result_type"] == "str"

    @pytest.mark.asyncio
    async def test_eval_returns_number(self, tmp_path):
        from camoufox_mcp.tools.javascript import JavaScriptService

        manager, page, _ = _make_session_manager(tmp_path)
        page.evaluate = AsyncMock(return_value=42)
        svc = JavaScriptService(manager)

        result = await svc.evaluate("s1", "1 + 41")

        assert result["result"] == 42
        assert result["result_type"] == "int"

    @pytest.mark.asyncio
    async def test_eval_returns_list(self, tmp_path):
        from camoufox_mcp.tools.javascript import JavaScriptService

        manager, page, _ = _make_session_manager(tmp_path)
        page.evaluate = AsyncMock(return_value=["a", "b"])
        svc = JavaScriptService(manager)

        result = await svc.evaluate("s1", "['a','b']")

        assert result["result"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_empty_expression_raises(self, tmp_path):
        from camoufox_mcp.tools.javascript import JavaScriptService
        from camoufox_mcp.utils.errors import SecurityError

        manager, _, _ = _make_session_manager(tmp_path)
        svc = JavaScriptService(manager)

        with pytest.raises(SecurityError):
            await svc.evaluate("s1", "")

    @pytest.mark.asyncio
    async def test_too_long_expression_raises(self, tmp_path):
        from camoufox_mcp.tools.javascript import JavaScriptService
        from camoufox_mcp.utils.errors import SecurityError

        manager, _, _ = _make_session_manager(tmp_path)
        svc = JavaScriptService(manager)

        with pytest.raises(SecurityError, match="too long"):
            await svc.evaluate("s1", "x" * 10_001)

    @pytest.mark.asyncio
    async def test_permission_block(self, tmp_path):
        from camoufox_mcp.security.permissions import PermissionRegistry, PermissionSet
        from camoufox_mcp.tools.javascript import JavaScriptService
        from camoufox_mcp.utils.errors import SecurityError

        manager, _, _ = _make_session_manager(tmp_path)
        reg = PermissionRegistry()
        reg.set_permissions("s1", PermissionSet(allow_javascript=False))
        svc = JavaScriptService(manager, permissions=reg)

        with pytest.raises(SecurityError, match="javascript_eval"):
            await svc.evaluate("s1", "document.title")

    @pytest.mark.asyncio
    async def test_browser_error_wrapped(self, tmp_path):
        from camoufox_mcp.tools.javascript import JavaScriptService
        from camoufox_mcp.utils.errors import JavaScriptError

        manager, page, _ = _make_session_manager(tmp_path)
        page.evaluate = AsyncMock(side_effect=Exception("SyntaxError: bad JS"))
        svc = JavaScriptService(manager)

        with pytest.raises(JavaScriptError, match="SyntaxError"):
            await svc.evaluate("s1", "{{invalid}")

    @pytest.mark.asyncio
    async def test_large_result_truncated(self, tmp_path):
        from camoufox_mcp.tools.javascript import JavaScriptService

        manager, page, _ = _make_session_manager(tmp_path)
        # Return a string larger than MAX_RESULT_LENGTH (100_000)
        huge_string = "x" * 200_000
        page.evaluate = AsyncMock(return_value=huge_string)
        svc = JavaScriptService(manager)

        result = await svc.evaluate("s1", "'x'.repeat(200000)")

        assert result["truncated"] is True
