"""
Camoufox MCP Server.

Responsibilities:
  1. Initialise configuration and logging.
  2. Initialise BrowserManager and service layer.
  3. Register all MCP tools.
  4. Run the MCP server over stdio transport.
  5. Handle graceful shutdown.

Phase 1 tools: browser_launch, browser_close, browser_sessions
Phase 2 tools: browser_open, browser_back, browser_forward, browser_reload,
               browser_tabs, browser_new_tab, browser_close_tab, browser_switch_tab,
               browser_session_info
Phase 3 tools: browser_click, browser_type, browser_press, browser_scroll, browser_wait
"""

from __future__ import annotations

import sys
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer

from camoufox_mcp.browser.manager import BrowserManager
from camoufox_mcp.config import Settings, get_settings
from camoufox_mcp.models.session import CloseSessionRequest, CreateSessionRequest
from camoufox_mcp.tools.downloads import DownloadService
from camoufox_mcp.tools.extraction import ExtractionService
from camoufox_mcp.tools.interaction import InteractionService
from camoufox_mcp.tools.javascript import JavaScriptService
from camoufox_mcp.tools.navigation import NavigationService
from camoufox_mcp.tools.screenshot import ScreenshotService
from camoufox_mcp.tools.sessions import SessionService
from camoufox_mcp.tools.tabs import TabService
from camoufox_mcp.tools.wait import WaitService
from camoufox_mcp.utils.errors import CamoufoxMCPError
from camoufox_mcp.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Helper: uniform error response
# --------------------------------------------------------------------------- #


def _err(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, CamoufoxMCPError):
        return {"success": False, **exc.to_dict()}
    logger.exception("Unexpected error")
    return {"success": False, "error": "InternalError", "message": str(exc)}


# --------------------------------------------------------------------------- #
# Server factory
# --------------------------------------------------------------------------- #


def build_server(settings: Settings) -> tuple[MCPServer, BrowserManager]:
    """Construct the MCPServer, BrowserManager, and all services."""
    browser = BrowserManager(settings)
    nav = NavigationService(browser)
    tabs = TabService(browser)
    sessions = SessionService(browser)
    interaction = InteractionService(browser)
    waiter = WaitService(browser)
    extractor = ExtractionService(browser)
    screenshotter = ScreenshotService(browser)
    downloader = DownloadService(browser)
    js_runner = JavaScriptService(browser)

    server = MCPServer(
        name="camoufox-mcp",
        description="Browser automation server for AI agents using Camoufox",
    )

    # ================================================================== #
    # Phase 1 — Browser lifecycle
    # ================================================================== #

    @server.tool(
        name="browser_launch",
        description=(
            "Launch a new browser session using Camoufox. "
            "Returns a session_id required by all other browser tools."
        ),
    )
    async def browser_launch(
        profile: Annotated[
            str, "Profile name (persistent storage bucket for this session)"
        ] = "default",
        headless: Annotated[bool, "Run browser without a visible window"] = True,
        humanize: Annotated[bool, "Enable Camoufox humanize mode (randomised timing)"] = False,
    ) -> dict[str, Any]:
        try:
            req = CreateSessionRequest(profile=profile, headless=headless, humanize=humanize)
            session_id = await browser.create_session(
                profile=req.profile,
                headless=req.headless,
                humanize=req.humanize,
                extra_options=req.extra_options or {},
            )
            info = next((s for s in browser.list_sessions() if s.session_id == session_id), None)
            return {
                "success": True,
                "session_id": session_id,
                "profile": req.profile,
                "headless": req.headless,
                "message": (
                    f"Browser session launched. "
                    f"Use session_id='{session_id}' for subsequent tool calls."
                ),
                **(info.model_dump() if info else {}),
            }
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_close",
        description="Close an existing browser session and release all its resources.",
    )
    async def browser_close(
        session_id: Annotated[str, "Session ID returned by browser_launch"],
    ) -> dict[str, Any]:
        try:
            req = CloseSessionRequest(session_id=session_id)
            await browser.close_session(req.session_id)
            return {
                "success": True,
                "session_id": req.session_id,
                "message": f"Session '{req.session_id}' closed successfully.",
            }
        except Exception as exc:
            return _err(exc)

    # ================================================================== #
    # Phase 2 — Session info
    # ================================================================== #

    @server.tool(
        name="browser_sessions",
        description="List all active browser sessions with their metadata.",
    )
    async def browser_sessions_tool() -> dict[str, Any]:
        return await sessions.list_sessions()

    @server.tool(
        name="browser_session_info",
        description=(
            "Get detailed information about a specific session, "
            "including open tabs and current URL."
        ),
    )
    async def browser_session_info(
        session_id: Annotated[str, "Session ID to inspect"],
    ) -> dict[str, Any]:
        try:
            return await sessions.get_session_info(session_id)
        except Exception as exc:
            return _err(exc)

    # ================================================================== #
    # Phase 2 — Navigation
    # ================================================================== #

    @server.tool(
        name="browser_open",
        description=(
            "Navigate the active tab of a session to a URL. "
            "Only http:// and https:// URLs are allowed."
        ),
    )
    async def browser_open(
        session_id: Annotated[str, "Session ID"],
        url: Annotated[str, "Destination URL (must be http:// or https://)"],
        wait_until: Annotated[
            str,
            "Load state to wait for: 'domcontentloaded' (default), 'load', or 'networkidle'",
        ] = "domcontentloaded",
        timeout: Annotated[
            int | None,
            "Navigation timeout in milliseconds (default: from server config)",
        ] = None,
    ) -> dict[str, Any]:
        try:
            return await nav.open(session_id, url, timeout=timeout, wait_until=wait_until)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_back",
        description="Navigate back in the browser history for the active tab.",
    )
    async def browser_back(
        session_id: Annotated[str, "Session ID"],
        timeout: Annotated[int | None, "Timeout in milliseconds"] = None,
    ) -> dict[str, Any]:
        try:
            return await nav.back(session_id, timeout=timeout)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_forward",
        description="Navigate forward in the browser history for the active tab.",
    )
    async def browser_forward(
        session_id: Annotated[str, "Session ID"],
        timeout: Annotated[int | None, "Timeout in milliseconds"] = None,
    ) -> dict[str, Any]:
        try:
            return await nav.forward(session_id, timeout=timeout)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_reload",
        description="Reload the current page in the active tab.",
    )
    async def browser_reload(
        session_id: Annotated[str, "Session ID"],
        timeout: Annotated[int | None, "Timeout in milliseconds"] = None,
    ) -> dict[str, Any]:
        try:
            return await nav.reload(session_id, timeout=timeout)
        except Exception as exc:
            return _err(exc)

    # ================================================================== #
    # Phase 2 — Tabs
    # ================================================================== #

    @server.tool(
        name="browser_tabs",
        description="List all open tabs in a session with their page_id, URL, and title.",
    )
    async def browser_tabs(
        session_id: Annotated[str, "Session ID"],
    ) -> dict[str, Any]:
        try:
            return await tabs.get_tabs(session_id)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_new_tab",
        description="Open a new tab in a session, optionally navigating to a URL.",
    )
    async def browser_new_tab(
        session_id: Annotated[str, "Session ID"],
        url: Annotated[str | None, "URL to open in the new tab (optional)"] = None,
    ) -> dict[str, Any]:
        try:
            return await tabs.new_tab(session_id, url=url)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_close_tab",
        description="Close a specific tab by its page_id.",
    )
    async def browser_close_tab(
        session_id: Annotated[str, "Session ID"],
        page_id: Annotated[str, "page_id of the tab to close (from browser_tabs)"],
    ) -> dict[str, Any]:
        try:
            return await tabs.close_tab(session_id, page_id)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_switch_tab",
        description="Switch the active tab in a session by page_id.",
    )
    async def browser_switch_tab(
        session_id: Annotated[str, "Session ID"],
        page_id: Annotated[str, "page_id of the tab to switch to (from browser_tabs)"],
    ) -> dict[str, Any]:
        try:
            return await tabs.switch_tab(session_id, page_id)
        except Exception as exc:
            return _err(exc)

    # ================================================================== #
    # Phase 3 — Interaction
    # ================================================================== #

    @server.tool(
        name="browser_click",
        description=(
            "Click an element on the current page. "
            "Supports CSS, XPath, ARIA role, text, label, and placeholder selectors."
        ),
    )
    async def browser_click(
        session_id: Annotated[str, "Session ID"],
        selector: Annotated[
            str,
            "Element selector. Examples: css=button.submit, role=button, "
            "text=Submit, label=Email, placeholder=Search, xpath=//button",
        ],
        button: Annotated[str, "Mouse button: 'left' (default), 'right', 'middle'"] = "left",
        click_count: Annotated[int, "Number of clicks: 1 (default) or 2 for double-click"] = 1,
        timeout: Annotated[int | None, "Timeout in ms to wait for element"] = None,
    ) -> dict[str, Any]:
        try:
            return await interaction.click(
                session_id,
                selector,
                timeout=timeout,
                button=button,
                click_count=click_count,
            )
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_type",
        description="Type text into an input element on the current page.",
    )
    async def browser_type(
        session_id: Annotated[str, "Session ID"],
        selector: Annotated[str, "Element selector (input, textarea, etc.)"],
        text: Annotated[str, "Text to type"],
        clear_first: Annotated[bool, "Clear the field before typing"] = False,
        delay: Annotated[int, "Delay between keystrokes in ms (0 = instant)"] = 0,
        timeout: Annotated[int | None, "Timeout in ms to wait for element"] = None,
    ) -> dict[str, Any]:
        try:
            return await interaction.type_text(
                session_id,
                selector,
                text,
                timeout=timeout,
                delay=delay,
                clear_first=clear_first,
            )
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_press",
        description=(
            "Press a keyboard key, optionally focused on a specific element. "
            "Examples: 'Enter', 'Escape', 'Tab', 'Control+a', 'Shift+Enter'."
        ),
    )
    async def browser_press(
        session_id: Annotated[str, "Session ID"],
        key: Annotated[
            str,
            "Key to press. Single char ('a'), named key ('Enter', 'Escape', 'Tab', 'ArrowDown'), "
            "or modifier combo ('Control+a', 'Shift+Enter', 'Meta+r').",
        ],
        selector: Annotated[str | None, "Optional element to focus before pressing key"] = None,
        timeout: Annotated[int | None, "Timeout in ms to wait for element"] = None,
    ) -> dict[str, Any]:
        try:
            return await interaction.press(session_id, key, selector=selector, timeout=timeout)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_scroll",
        description=(
            "Scroll the page or a specific element. Positive y scrolls down, negative y scrolls up."
        ),
    )
    async def browser_scroll(
        session_id: Annotated[str, "Session ID"],
        x: Annotated[int, "Horizontal scroll delta in pixels"] = 0,
        y: Annotated[int, "Vertical scroll delta in pixels (positive = down)"] = 500,
        selector: Annotated[
            str | None, "Optional element to scroll within (scrolls page if not set)"
        ] = None,
        timeout: Annotated[int | None, "Timeout in ms to wait for element"] = None,
    ) -> dict[str, Any]:
        try:
            return await interaction.scroll(session_id, x, y, selector=selector, timeout=timeout)
        except Exception as exc:
            return _err(exc)

    # ================================================================== #
    # Phase 3 — Wait
    # ================================================================== #

    @server.tool(
        name="browser_wait",
        description=(
            "Wait for a condition before continuing. "
            "Specify exactly one of: selector, url, load_state, or timeout_ms. "
            "Prefer selector/url/load_state over timeout_ms."
        ),
    )
    async def browser_wait(
        session_id: Annotated[str, "Session ID"],
        selector: Annotated[
            str | None,
            "Wait until this element reaches the given state (default: visible)",
        ] = None,
        url: Annotated[
            str | None,
            "Wait until the page URL contains this string or matches this regex",
        ] = None,
        load_state: Annotated[
            str | None,
            "Wait for page load state: 'domcontentloaded', 'load', or 'networkidle'",
        ] = None,
        timeout_ms: Annotated[
            int | None,
            "Fixed wait in milliseconds (use only as last resort, max 30000)",
        ] = None,
        state: Annotated[
            str,
            "Element state for selector wait: 'visible' (default), 'attached', 'hidden', 'detached'",
        ] = "visible",
        timeout: Annotated[int | None, "Maximum wait timeout in ms"] = None,
    ) -> dict[str, Any]:
        try:
            return await waiter.wait(
                session_id,
                selector=selector,
                url=url,
                load_state=load_state,
                timeout_ms=timeout_ms,
                timeout=timeout,
                state=state,
            )
        except Exception as exc:
            return _err(exc)

    # ================================================================== #
    # Phase 4 — Extraction
    # ================================================================== #

    @server.tool(
        name="browser_extract_text",
        description=(
            "Extract visible plain text from the current page. "
            "Respects CSS visibility — excludes hidden elements, scripts, and styles. "
            "Returns truncated text if content exceeds max_length."
        ),
    )
    async def browser_extract_text(
        session_id: Annotated[str, "Session ID"],
        selector: Annotated[
            str | None,
            "Optional CSS selector to extract text from a specific element only",
        ] = None,
        max_length: Annotated[
            int | None,
            "Maximum characters to return (default: from server config, typically 50000)",
        ] = None,
    ) -> dict[str, Any]:
        try:
            return await extractor.get_text(session_id, max_length=max_length, selector=selector)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_extract_html",
        description=(
            "Extract HTML source from the current page or a specific element. "
            "Full page HTML can be very large — use a selector to narrow scope when possible."
        ),
    )
    async def browser_extract_html(
        session_id: Annotated[str, "Session ID"],
        selector: Annotated[
            str | None,
            "Optional CSS selector to extract HTML from a specific element only",
        ] = None,
        outer: Annotated[
            bool,
            "If True (default), return outerHTML (includes the element tag). "
            "If False, return innerHTML (children only).",
        ] = True,
        max_length: Annotated[
            int | None,
            "Maximum characters to return (default: from server config, typically 200000)",
        ] = None,
    ) -> dict[str, Any]:
        try:
            return await extractor.get_html(
                session_id, max_length=max_length, selector=selector, outer=outer
            )
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_extract_links",
        description=(
            "Extract all hyperlinks from the current page. "
            "Returns href, link text, and rel attribute for each link."
        ),
    )
    async def browser_extract_links(
        session_id: Annotated[str, "Session ID"],
        max_links: Annotated[int, "Maximum number of links to return (default: 200)"] = 200,
    ) -> dict[str, Any]:
        try:
            return await extractor.get_links(session_id, max_links=max_links)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_extract_metadata",
        description=(
            "Extract page metadata: title, description, Open Graph tags, "
            "Twitter Card tags, canonical URL, language, and robots directives."
        ),
    )
    async def browser_extract_metadata(
        session_id: Annotated[str, "Session ID"],
    ) -> dict[str, Any]:
        try:
            return await extractor.get_metadata(session_id)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_extract_tables",
        description=(
            "Extract all HTML tables from the current page as structured data. "
            "Each table is returned as a list of rows, where each row is a list of cell values."
        ),
    )
    async def browser_extract_tables(
        session_id: Annotated[str, "Session ID"],
        max_tables: Annotated[int, "Maximum number of tables to return (default: 20)"] = 20,
    ) -> dict[str, Any]:
        try:
            return await extractor.get_tables(session_id, max_tables=max_tables)
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_extract_headings",
        description=(
            "Extract all headings (h1–h6) from the current page "
            "with their level and text content. Useful for understanding page structure."
        ),
    )
    async def browser_extract_headings(
        session_id: Annotated[str, "Session ID"],
    ) -> dict[str, Any]:
        try:
            return await extractor.get_headings(session_id)
        except Exception as exc:
            return _err(exc)

    # ================================================================== #
    # Phase 5 — Screenshot
    # ================================================================== #

    @server.tool(
        name="browser_screenshot",
        description=(
            "Take a screenshot of the current page. "
            "Returns the file path where the screenshot was saved. "
            "Modes: 'viewport' (default, visible area), 'full_page' (entire page), "
            "'element' (specific element, requires selector)."
        ),
    )
    async def browser_screenshot(
        session_id: Annotated[str, "Session ID"],
        mode: Annotated[
            str,
            "Screenshot mode: 'viewport' (default), 'full_page', or 'element'",
        ] = "viewport",
        selector: Annotated[
            str | None,
            "Element selector required when mode='element'",
        ] = None,
        filename: Annotated[
            str | None,
            "Optional base filename (auto-generated if not provided)",
        ] = None,
        image_format: Annotated[
            str,
            "Image format: 'png' (default) or 'jpeg'",
        ] = "png",
        quality: Annotated[
            int | None,
            "JPEG quality 1–100 (only for jpeg format)",
        ] = None,
    ) -> dict[str, Any]:
        try:
            return await screenshotter.take(
                session_id,
                mode=mode,
                selector=selector,
                filename=filename,
                image_format=image_format,
                quality=quality,
            )
        except Exception as exc:
            return _err(exc)

    # ================================================================== #
    # Phase 5 — Downloads
    # ================================================================== #

    @server.tool(
        name="browser_download_start",
        description=(
            "Download a file from a URL into the server's controlled download directory. "
            "Returns the local file path after download completes."
        ),
    )
    async def browser_download_start(
        session_id: Annotated[str, "Session ID"],
        url: Annotated[str, "Direct download URL (must be http:// or https://)"],
        filename: Annotated[
            str | None,
            "Optional output filename (auto-derived from URL if not provided)",
        ] = None,
        timeout: Annotated[
            int | None,
            "Download timeout in milliseconds",
        ] = None,
    ) -> dict[str, Any]:
        try:
            return await downloader.start_download(
                session_id, url, filename=filename, timeout=timeout
            )
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_download_list",
        description="List all files currently in the download directory.",
    )
    async def browser_download_list() -> dict[str, Any]:
        try:
            return await downloader.list_downloads()
        except Exception as exc:
            return _err(exc)

    @server.tool(
        name="browser_download_clear",
        description="Delete all files from the download directory.",
    )
    async def browser_download_clear() -> dict[str, Any]:
        try:
            return await downloader.clear_downloads()
        except Exception as exc:
            return _err(exc)

    # ================================================================== #
    # Phase 5 — JavaScript
    # ================================================================== #

    @server.tool(
        name="browser_eval",
        description=(
            "Evaluate a JavaScript expression in the current page context. "
            "Runs inside the browser sandbox — cannot access server filesystem. "
            "Examples: 'document.title', '() => document.querySelectorAll(\"a\").length', "
            "'window.location.href'."
        ),
    )
    async def browser_eval(
        session_id: Annotated[str, "Session ID"],
        expression: Annotated[
            str,
            "JavaScript expression or arrow function to evaluate in the browser context",
        ],
        timeout: Annotated[
            int | None,
            "Evaluation timeout in milliseconds",
        ] = None,
    ) -> dict[str, Any]:
        try:
            return await js_runner.evaluate(session_id, expression, timeout=timeout)
        except Exception as exc:
            return _err(exc)

    return server, browser


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


async def run(settings: Settings | None = None) -> None:
    """Start the MCP server and block until it exits."""
    if settings is None:
        settings = get_settings()

    setup_logging(level=settings.log_level, json_logs=settings.log_json)
    logger.info("Starting Camoufox MCP server")

    server, browser = build_server(settings)

    try:
        await browser.start()
        await server.run_stdio_async()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — shutting down")
    except Exception:
        logger.exception("Fatal error in MCP server")
        sys.exit(1)
    finally:
        await browser.shutdown()
        logger.info("Camoufox MCP server stopped")
