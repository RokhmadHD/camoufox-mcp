"""
Unit tests for Phase 4 — extraction engine (no browser launch required).

All tests mock the Playwright Page to avoid needing a real browser.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_page(url="https://example.com", title="Test Page") -> MagicMock:
    """Return a minimal mock Page with url and async title()."""
    page = MagicMock()
    page.url = url
    page.title = AsyncMock(return_value=title)
    return page


def _page_with_evaluate(url="https://example.com", title="Test Page", return_value=None):
    """Return a mock Page with a single evaluate return_value."""
    page = _make_page(url, title)
    page.evaluate = AsyncMock(return_value=return_value)
    return page


def _page_with_text(text: str, url="https://example.com", title="Test Page"):
    """Mock Page that returns text from evaluate."""
    page = _make_page(url, title)
    page.evaluate = AsyncMock(return_value=text)
    return page


def _page_with_html(html: str, url="https://example.com", title="Test Page"):
    """Mock Page that returns html from content()."""
    page = _make_page(url, title)
    page.content = AsyncMock(return_value=html)
    return page


# --------------------------------------------------------------------------- #
# extract_text
# --------------------------------------------------------------------------- #


class TestExtractText:
    @pytest.mark.asyncio
    async def test_basic_extraction(self):
        from camoufox_mcp.extraction.text import extract_text

        page = _page_with_text("Hello world from test")
        result = await extract_text(page)

        assert result["text"] == "Hello world from test"
        assert result["url"] == "https://example.com"
        assert result["title"] == "Test Page"
        assert result["truncated"] is False
        assert result["char_count"] == len("Hello world from test")

    @pytest.mark.asyncio
    async def test_truncation(self):
        from camoufox_mcp.extraction.text import extract_text

        long_text = "a" * 1000
        page = _page_with_text(long_text)
        result = await extract_text(page, max_length=100)

        assert len(result["text"]) == 100
        assert result["truncated"] is True
        assert result["char_count"] == 100

    @pytest.mark.asyncio
    async def test_no_truncation_when_within_limit(self):
        from camoufox_mcp.extraction.text import extract_text

        page = _page_with_text("short text")
        result = await extract_text(page, max_length=1000)

        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_empty_body_returns_empty_string(self):
        from camoufox_mcp.extraction.text import extract_text

        page = _page_with_text("")
        result = await extract_text(page)

        assert result["text"] == ""
        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_whitespace_normalisation(self):
        from camoufox_mcp.extraction.text import extract_text

        page = _page_with_text("line1\n\n\n\n\nline2")
        result = await extract_text(page)

        # Three+ consecutive newlines should collapse to two
        assert "\n\n\n" not in result["text"]

    @pytest.mark.asyncio
    async def test_selector_uses_locator(self):
        from camoufox_mcp.extraction.text import extract_text

        page = _make_page()
        mock_first = MagicMock()
        mock_first.inner_text = AsyncMock(return_value="element text")
        mock_locator = MagicMock()
        mock_locator.first = mock_first
        page.locator = MagicMock(return_value=mock_locator)

        result = await extract_text(page, selector="css=.content")
        assert result["text"] == "element text"
        assert result["selector"] == "css=.content"


# --------------------------------------------------------------------------- #
# extract_html
# --------------------------------------------------------------------------- #


class TestExtractHtml:
    @pytest.mark.asyncio
    async def test_full_page_html(self):
        from camoufox_mcp.extraction.html import extract_html

        page = _page_with_html("<html><body>test</body></html>")
        result = await extract_html(page)

        assert "<body>" in result["html"]
        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_html_truncation(self):
        from camoufox_mcp.extraction.html import extract_html

        big_html = "<div>" + "x" * 10_000 + "</div>"
        page = _page_with_html(big_html)
        result = await extract_html(page, max_length=100)

        assert len(result["html"]) == 100
        assert result["truncated"] is True

    @pytest.mark.asyncio
    async def test_returns_url_and_title(self):
        from camoufox_mcp.extraction.html import extract_html

        page = _page_with_html("<html></html>", url="https://test.com", title="My Page")
        result = await extract_html(page)

        assert result["url"] == "https://test.com"
        assert result["title"] == "My Page"

    @pytest.mark.asyncio
    async def test_selector_outer_html(self):
        from camoufox_mcp.extraction.html import extract_html

        page = _make_page()
        mock_first = MagicMock()
        mock_first.evaluate = AsyncMock(return_value="<div>content</div>")
        mock_locator = MagicMock()
        mock_locator.first = mock_first
        page.locator = MagicMock(return_value=mock_locator)

        result = await extract_html(page, selector="css=div")
        assert result["html"] == "<div>content</div>"

    @pytest.mark.asyncio
    async def test_selector_inner_html(self):
        from camoufox_mcp.extraction.html import extract_html

        page = _make_page()
        mock_first = MagicMock()
        mock_first.inner_html = AsyncMock(return_value="<span>inner</span>")
        mock_locator = MagicMock()
        mock_locator.first = mock_first
        page.locator = MagicMock(return_value=mock_locator)

        result = await extract_html(page, selector="css=div", outer=False)
        assert result["html"] == "<span>inner</span>"


# --------------------------------------------------------------------------- #
# extract_links
# --------------------------------------------------------------------------- #


class TestExtractLinks:
    @pytest.mark.asyncio
    async def test_basic_links(self):
        from camoufox_mcp.extraction.structured import extract_links

        links_data = [
            {"href": "https://example.com/a", "text": "Link A", "rel": ""},
            {"href": "https://example.com/b", "text": "Link B", "rel": "nofollow"},
        ]
        page = _page_with_evaluate(return_value=links_data)
        result = await extract_links(page)

        assert result["link_count"] == 2
        assert result["links"][0]["href"] == "https://example.com/a"
        assert result["truncated"] is False

    @pytest.mark.asyncio
    async def test_link_max_limit(self):
        from camoufox_mcp.extraction.structured import extract_links

        links_data = [
            {"href": f"https://example.com/{i}", "text": f"Link {i}", "rel": ""} for i in range(50)
        ]
        page = _page_with_evaluate(return_value=links_data)
        result = await extract_links(page, max_links=10)

        assert result["link_count"] == 10
        assert result["truncated"] is True

    @pytest.mark.asyncio
    async def test_empty_links(self):
        from camoufox_mcp.extraction.structured import extract_links

        page = _page_with_evaluate(return_value=[])
        result = await extract_links(page)

        assert result["link_count"] == 0
        assert result["links"] == []


# --------------------------------------------------------------------------- #
# extract_metadata
# --------------------------------------------------------------------------- #


class TestExtractMetadata:
    @pytest.mark.asyncio
    async def test_basic_metadata(self):
        from camoufox_mcp.extraction.structured import extract_metadata

        meta = {
            "title": "My Page",
            "url": "https://example.com",
            "description": "A test page",
            "lang": "en",
        }
        page = _page_with_evaluate(return_value=meta)
        result = await extract_metadata(page)

        assert result["title"] == "My Page"
        assert result["metadata"]["description"] == "A test page"
        assert result["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_og_metadata(self):
        from camoufox_mcp.extraction.structured import extract_metadata

        meta = {
            "title": "OG Page",
            "url": "https://example.com",
            "og": {"title": "OG Title", "image": "https://example.com/img.png"},
            "lang": "en",
        }
        page = _page_with_evaluate(return_value=meta)
        result = await extract_metadata(page)

        assert result["metadata"]["og"]["title"] == "OG Title"


# --------------------------------------------------------------------------- #
# extract_tables
# --------------------------------------------------------------------------- #


class TestExtractTables:
    @pytest.mark.asyncio
    async def test_basic_table(self):
        from camoufox_mcp.extraction.structured import extract_tables

        tables_data = [
            {
                "caption": "Sales Data",
                "rows": [["Name", "Value"], ["Alice", "100"], ["Bob", "200"]],
                "row_count": 3,
                "col_count": 2,
            }
        ]
        page = _page_with_evaluate(return_value=tables_data)
        result = await extract_tables(page)

        assert result["table_count"] == 1
        assert result["tables"][0]["rows"][0] == ["Name", "Value"]
        assert result["tables"][0]["caption"] == "Sales Data"

    @pytest.mark.asyncio
    async def test_max_tables_limit(self):
        from camoufox_mcp.extraction.structured import extract_tables

        tables_data = [
            {"caption": None, "rows": [["A"]], "row_count": 1, "col_count": 1} for _ in range(30)
        ]
        page = _page_with_evaluate(return_value=tables_data)
        result = await extract_tables(page, max_tables=5)

        assert result["table_count"] == 5
        assert result["truncated"] is True

    @pytest.mark.asyncio
    async def test_empty_tables(self):
        from camoufox_mcp.extraction.structured import extract_tables

        page = _page_with_evaluate(return_value=[])
        result = await extract_tables(page)

        assert result["table_count"] == 0


# --------------------------------------------------------------------------- #
# extract_headings
# --------------------------------------------------------------------------- #


class TestExtractHeadings:
    @pytest.mark.asyncio
    async def test_basic_headings(self):
        from camoufox_mcp.extraction.structured import extract_headings

        headings_data = [
            {"level": 1, "text": "Main Title"},
            {"level": 2, "text": "Section One"},
            {"level": 3, "text": "Subsection"},
        ]
        page = _page_with_evaluate(return_value=headings_data)
        result = await extract_headings(page)

        assert result["heading_count"] == 3
        assert result["headings"][0]["level"] == 1
        assert result["headings"][0]["text"] == "Main Title"

    @pytest.mark.asyncio
    async def test_empty_headings(self):
        from camoufox_mcp.extraction.structured import extract_headings

        page = _page_with_evaluate(return_value=[])
        result = await extract_headings(page)

        assert result["heading_count"] == 0
        assert result["headings"] == []


# --------------------------------------------------------------------------- #
# ExtractionService (mocked BrowserManager)
# --------------------------------------------------------------------------- #


@pytest.fixture
def mock_browser_for_extraction(tmp_path):
    from camoufox_mcp.browser.manager import BrowserManager, _Session
    from camoufox_mcp.config import Settings

    settings = Settings(
        profile_dir=tmp_path / "profiles",
        download_dir=tmp_path / "downloads",
        screenshot_dir=tmp_path / "screenshots",
        max_text_length=50_000,
        max_html_length=200_000,
    )
    manager = BrowserManager(settings)

    # Build page mock with separate evaluate mocks per call using side_effect list
    page = _make_page()
    page.content = AsyncMock(return_value="<html><body>Sample</body></html>")
    # evaluate returns different data per invocation type — use side_effect with list
    page.evaluate = AsyncMock(
        side_effect=[
            # text extraction calls
            "Sample page text content",
            # links extraction
            [{"href": "https://example.com/about", "text": "About", "rel": ""}],
            # metadata
            {"title": "Test Page", "url": "https://example.com", "lang": "en"},
            # tables
            [],
            # headings
            [{"level": 1, "text": "Sample Heading"}],
        ]
    )

    fake_session = MagicMock(spec=_Session)
    fake_session.session_id = "session_test"
    fake_session.touch = MagicMock()
    manager._sessions["session_test"] = fake_session

    async def _get_active_page(sid):
        return page

    manager.get_active_page = _get_active_page
    return manager, page


class TestExtractionService:
    @pytest.mark.asyncio
    async def test_get_text(self, tmp_path):
        from camoufox_mcp.browser.manager import BrowserManager, _Session
        from camoufox_mcp.config import Settings
        from camoufox_mcp.tools.extraction import ExtractionService

        settings = Settings(
            profile_dir=tmp_path / "profiles",
            download_dir=tmp_path / "downloads",
            screenshot_dir=tmp_path / "screenshots",
        )
        manager = BrowserManager(settings)
        page = _page_with_text("Sample page text content")
        fake_session = MagicMock(spec=_Session)
        fake_session.touch = MagicMock()
        manager._sessions["s1"] = fake_session

        async def _gap(_):
            return page

        manager.get_active_page = _gap
        svc = ExtractionService(manager)
        result = await svc.get_text("s1")

        assert result["success"] is True
        assert result["text"] == "Sample page text content"
        assert result["session_id"] == "s1"

    @pytest.mark.asyncio
    async def test_get_html(self, tmp_path):
        from camoufox_mcp.browser.manager import BrowserManager, _Session
        from camoufox_mcp.config import Settings
        from camoufox_mcp.tools.extraction import ExtractionService

        settings = Settings(
            profile_dir=tmp_path / "profiles",
            download_dir=tmp_path / "downloads",
            screenshot_dir=tmp_path / "screenshots",
        )
        manager = BrowserManager(settings)
        page = _page_with_html("<html><body>Sample</body></html>")
        fake_session = MagicMock(spec=_Session)
        fake_session.touch = MagicMock()
        manager._sessions["s1"] = fake_session

        async def _gap(_):
            return page

        manager.get_active_page = _gap
        svc = ExtractionService(manager)
        result = await svc.get_html("s1")

        assert result["success"] is True
        assert "<body>" in result["html"]

    @pytest.mark.asyncio
    async def test_get_links(self, tmp_path):
        from camoufox_mcp.browser.manager import BrowserManager, _Session
        from camoufox_mcp.config import Settings
        from camoufox_mcp.tools.extraction import ExtractionService

        settings = Settings(
            profile_dir=tmp_path / "profiles",
            download_dir=tmp_path / "downloads",
            screenshot_dir=tmp_path / "screenshots",
        )
        manager = BrowserManager(settings)
        links_data = [{"href": "https://example.com/about", "text": "About", "rel": ""}]
        page = _page_with_evaluate(return_value=links_data)
        fake_session = MagicMock(spec=_Session)
        fake_session.touch = MagicMock()
        manager._sessions["s1"] = fake_session

        async def _gap(_):
            return page

        manager.get_active_page = _gap
        svc = ExtractionService(manager)
        result = await svc.get_links("s1")

        assert result["success"] is True
        assert result["link_count"] == 1
        assert result["links"][0]["text"] == "About"

    @pytest.mark.asyncio
    async def test_get_metadata(self, tmp_path):
        from camoufox_mcp.browser.manager import BrowserManager, _Session
        from camoufox_mcp.config import Settings
        from camoufox_mcp.tools.extraction import ExtractionService

        settings = Settings(
            profile_dir=tmp_path / "profiles",
            download_dir=tmp_path / "downloads",
            screenshot_dir=tmp_path / "screenshots",
        )
        manager = BrowserManager(settings)
        meta = {"title": "Test Page", "url": "https://example.com", "lang": "en"}
        page = _page_with_evaluate(return_value=meta)
        fake_session = MagicMock(spec=_Session)
        fake_session.touch = MagicMock()
        manager._sessions["s1"] = fake_session

        async def _gap(_):
            return page

        manager.get_active_page = _gap
        svc = ExtractionService(manager)
        result = await svc.get_metadata("s1")

        assert result["success"] is True
        assert result["title"] == "Test Page"
        assert "lang" in result["metadata"]

    @pytest.mark.asyncio
    async def test_get_headings(self, tmp_path):
        from camoufox_mcp.browser.manager import BrowserManager, _Session
        from camoufox_mcp.config import Settings
        from camoufox_mcp.tools.extraction import ExtractionService

        settings = Settings(
            profile_dir=tmp_path / "profiles",
            download_dir=tmp_path / "downloads",
            screenshot_dir=tmp_path / "screenshots",
        )
        manager = BrowserManager(settings)
        headings_data = [{"level": 1, "text": "Sample Heading"}]
        page = _page_with_evaluate(return_value=headings_data)
        fake_session = MagicMock(spec=_Session)
        fake_session.touch = MagicMock()
        manager._sessions["s1"] = fake_session

        async def _gap(_):
            return page

        manager.get_active_page = _gap
        svc = ExtractionService(manager)
        result = await svc.get_headings("s1")

        assert result["success"] is True
        assert result["heading_count"] == 1
        assert result["headings"][0]["text"] == "Sample Heading"

    @pytest.mark.asyncio
    async def test_get_tables_empty(self, tmp_path):
        from camoufox_mcp.browser.manager import BrowserManager, _Session
        from camoufox_mcp.config import Settings
        from camoufox_mcp.tools.extraction import ExtractionService

        settings = Settings(
            profile_dir=tmp_path / "profiles",
            download_dir=tmp_path / "downloads",
            screenshot_dir=tmp_path / "screenshots",
        )
        manager = BrowserManager(settings)
        page = _page_with_evaluate(return_value=[])
        fake_session = MagicMock(spec=_Session)
        fake_session.touch = MagicMock()
        manager._sessions["s1"] = fake_session

        async def _gap(_):
            return page

        manager.get_active_page = _gap
        svc = ExtractionService(manager)
        result = await svc.get_tables("s1")

        assert result["success"] is True
        assert result["table_count"] == 0

    @pytest.mark.asyncio
    async def test_session_not_found_raises(self, tmp_path):
        from camoufox_mcp.browser.manager import BrowserManager
        from camoufox_mcp.config import Settings
        from camoufox_mcp.tools.extraction import ExtractionService
        from camoufox_mcp.utils.errors import SessionNotFoundError

        settings = Settings(
            profile_dir=tmp_path / "profiles",
            download_dir=tmp_path / "downloads",
            screenshot_dir=tmp_path / "screenshots",
        )
        manager = BrowserManager(settings)
        svc = ExtractionService(manager)

        with pytest.raises(SessionNotFoundError):
            await svc.get_text("bad_session_id")
