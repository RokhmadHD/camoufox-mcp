"""
BrowserManager — owns the Camoufox browser lifecycle.

Responsibilities:
  - Launch one Camoufox instance per session (not a shared singleton).
  - Track all active sessions and their contexts/pages.
  - Prevent orphaned contexts and resource leaks.
  - Provide a clean async context manager interface.

Architecture note:
  BrowserManager does NOT know about MCP.
  MCP tools call SessionManager, which delegates to BrowserManager.
  This keeps the browser layer independently testable.

Camoufox note:
  AsyncCamoufox is a context manager that returns a BrowserContext directly
  (not a Browser → Context pair as in standard Playwright).
  We store the context and manage pages inside it.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import ulid

from camoufox_mcp.config import Settings
from camoufox_mcp.models.session import SessionInfo, SessionStatus
from camoufox_mcp.utils.errors import (
    BrowserError,
    SessionLimitError,
    SessionNotFoundError,
)
from camoufox_mcp.utils.logging import get_logger

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Internal session record
# --------------------------------------------------------------------------- #


class _Session:
    """Internal container for a live browser session.

    Not exposed to MCP clients — use SessionInfo for serialised snapshots.
    """

    def __init__(
        self,
        session_id: str,
        context: BrowserContext,
        profile: str,
        headless: bool,
    ) -> None:
        self.session_id = session_id
        self.context = context
        self.profile = profile
        self.headless = headless
        self.status = SessionStatus.ACTIVE
        self.created_at = datetime.now(tz=UTC)
        self.last_activity = self.created_at
        # The context manager returned by AsyncCamoufox — kept so we can
        # call __aexit__ cleanly on close.
        self._cm: Any = None

    def touch(self) -> None:
        """Update last_activity timestamp."""
        self.last_activity = datetime.now(tz=UTC)

    def active_page(self) -> Page | None:
        """Return the most recently used page, or None if no pages exist."""
        pages = self.context.pages
        return pages[-1] if pages else None

    def to_info(self) -> SessionInfo:
        active = self.active_page()
        return SessionInfo(
            session_id=self.session_id,
            status=self.status,
            profile=self.profile,
            headless=self.headless,
            created_at=self.created_at,
            last_activity=self.last_activity,
            page_count=len(self.context.pages),
            active_url=active.url if active else None,
        )


# --------------------------------------------------------------------------- #
# BrowserManager
# --------------------------------------------------------------------------- #


class BrowserManager:
    """
    Manages the full lifecycle of Camoufox browser sessions.

    Usage::

        manager = BrowserManager(settings)
        await manager.start()   # no-op for now, reserved for future pool init
        ...
        session_id = await manager.create_session()
        context = manager.get_context(session_id)
        ...
        await manager.close_session(session_id)
        await manager.shutdown()
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sessions: dict[str, _Session] = {}
        self._lock = asyncio.Lock()
        self._started = False

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Initialise the manager (idempotent)."""
        if self._started:
            return
        # Ensure data directories exist
        for path in (
            self._settings.profile_dir,
            self._settings.download_dir,
            self._settings.screenshot_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self._started = True
        logger.info("BrowserManager started")

    async def shutdown(self) -> None:
        """Close all active sessions and clean up resources."""
        logger.info("BrowserManager shutting down", extra={"active_sessions": len(self._sessions)})
        session_ids = list(self._sessions.keys())
        for sid in session_ids:
            try:
                await self.close_session(sid)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Error closing session during shutdown",
                    extra={"session_id": sid, "error": str(exc)},
                )
        self._started = False
        logger.info("BrowserManager shutdown complete")

    # ------------------------------------------------------------------ #
    # Session creation
    # ------------------------------------------------------------------ #

    async def create_session(
        self,
        profile: str = "default",
        headless: bool | None = None,
        humanize: bool | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> str:
        """
        Launch a new Camoufox browser context and register a session.

        Args:
            profile:       Profile name (maps to a subdirectory under profile_dir).
            headless:      Override the global headless setting for this session.
            humanize:      Enable Camoufox humanize mode for this session.
            extra_options: Additional kwargs forwarded to AsyncCamoufox.

        Returns:
            The new session_id string.

        Raises:
            SessionLimitError: If max_sessions is already reached.
            BrowserError:      If Camoufox fails to launch.
        """
        async with self._lock:
            if len(self._sessions) >= self._settings.max_sessions:
                raise SessionLimitError(self._settings.max_sessions)

        session_id = f"session_{ulid.new()}"
        _headless = headless if headless is not None else self._settings.headless
        _humanize = humanize if humanize is not None else self._settings.humanize

        profile_path = self._settings.profile_dir / profile
        profile_path.mkdir(parents=True, exist_ok=True)

        launch_kwargs: dict[str, Any] = {
            "headless": _headless,
            "humanize": _humanize,
            "persistent_context": True,
            "user_data_dir": str(profile_path),
            **(extra_options or {}),
        }

        logger.info(
            "Launching browser session",
            extra={"session_id": session_id, "profile": profile, "headless": _headless},
        )

        try:
            from camoufox.async_api import AsyncCamoufox  # type: ignore[import]

            cm = AsyncCamoufox(**launch_kwargs)
            context: BrowserContext = await cm.__aenter__()
        except Exception as exc:
            raise BrowserError(
                f"Failed to launch Camoufox browser: {exc}",
                details=str(exc),
            ) from exc

        session = _Session(
            session_id=session_id,
            context=context,
            profile=profile,
            headless=_headless,
        )
        session._cm = cm

        async with self._lock:
            self._sessions[session_id] = session

        logger.info(
            "Browser session created",
            extra={"session_id": session_id, "profile": profile},
        )
        return session_id

    # ------------------------------------------------------------------ #
    # Session access
    # ------------------------------------------------------------------ #

    def get_session(self, session_id: str) -> _Session:
        """
        Return the internal session record.

        Raises:
            SessionNotFoundError: If the session_id is not registered.
        """
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def get_context(self, session_id: str) -> BrowserContext:
        """Return the Playwright BrowserContext for a session."""
        return self.get_session(session_id).context

    async def get_active_page(self, session_id: str) -> Page:
        """
        Return the active page for a session, creating one if none exists.

        Raises:
            SessionNotFoundError: If the session_id is not registered.
            BrowserError:         If a new page cannot be created.
        """
        session = self.get_session(session_id)
        session.touch()

        page = session.active_page()
        if page is None:
            try:
                page = await session.context.new_page()
            except Exception as exc:
                raise BrowserError(
                    f"Failed to create a new page in session '{session_id}': {exc}"
                ) from exc
        return page

    # ------------------------------------------------------------------ #
    # Session close
    # ------------------------------------------------------------------ #

    async def close_session(self, session_id: str) -> None:
        """
        Close the browser context for a session and remove it from the registry.

        Raises:
            SessionNotFoundError: If the session_id is not registered.
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(session_id)
            session.status = SessionStatus.CLOSING

        try:
            if session._cm is not None:
                await session._cm.__aexit__(None, None, None)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Error during browser context exit",
                extra={"session_id": session_id, "error": str(exc)},
            )
        finally:
            async with self._lock:
                self._sessions.pop(session_id, None)

        logger.info("Browser session closed", extra={"session_id": session_id})

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #

    def list_sessions(self) -> list[SessionInfo]:
        """Return a serialisable snapshot of all active sessions."""
        return [s.to_info() for s in self._sessions.values()]

    def session_count(self) -> int:
        return len(self._sessions)

    def is_started(self) -> bool:
        return self._started
