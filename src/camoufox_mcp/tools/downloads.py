"""
DownloadService — handles browser download management.

Downloads are routed to a single controlled directory (CAMOUFOX_DOWNLOAD_DIR).

Security:
    - All download paths are validated to stay inside download_dir
    - Path traversal is rejected
    - Filename sanitisation prevents dangerous filenames

The service provides:
    browser_download_start   Trigger a download from a URL
    browser_download_list    List files in the download directory
    browser_download_clear   Clear the download directory
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Any

from camoufox_mcp.browser.manager import BrowserManager
from camoufox_mcp.utils.errors import DownloadError, PathTraversalError, SecurityError
from camoufox_mcp.utils.logging import get_logger

logger = get_logger(__name__)

# Characters not allowed in safe filenames
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Max filename length
_MAX_FILENAME_LEN = 255


def _sanitise_filename(name: str) -> str:
    """
    Return a safe filename derived from an arbitrary string.

    Replaces unsafe characters with underscores, collapses path traversal
    sequences, and strips leading dots/spaces.
    """
    name = _UNSAFE_CHARS.sub("_", name)
    # Collapse any remaining path traversal sequences (e.g. ".." after replace)
    import re as _re

    name = _re.sub(r"\.{2,}", "_", name)
    name = name.strip(". ")
    name = name[:_MAX_FILENAME_LEN]
    if not name:
        name = "download"
    return name


def _validate_download_path(path: Path, download_dir: Path) -> None:
    """
    Raise PathTraversalError if path escapes download_dir.

    Args:
        path:         The candidate file path.
        download_dir: The allowed base directory.

    Raises:
        PathTraversalError: If path is outside download_dir.
    """
    try:
        resolved = path.resolve()
        base = download_dir.resolve()
        if not str(resolved).startswith(str(base)):
            raise PathTraversalError(str(path))
    except PathTraversalError:
        raise
    except Exception as exc:
        raise SecurityError(f"Could not validate download path: {exc}") from exc


class DownloadService:
    """
    Service layer for download operations.

    Args:
        browser: The shared BrowserManager instance.
    """

    def __init__(self, browser: BrowserManager) -> None:
        self._browser = browser

    @property
    def _download_dir(self) -> Path:
        return self._browser._settings.download_dir

    # ------------------------------------------------------------------ #
    # browser_download_start
    # ------------------------------------------------------------------ #

    async def start_download(
        self,
        session_id: str,
        url: str,
        *,
        filename: str | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """
        Download a file from a URL into the controlled download directory.

        Uses Playwright's expect_download() context to intercept the download
        triggered by navigating to or clicking a download link.

        Args:
            session_id: Target session.
            url:        Direct download URL.
            filename:   Optional output filename (sanitised). Auto-derived if None.
            timeout:    Download timeout in ms.

        Returns:
            Dict with success, session_id, path, filename, size_bytes.

        Raises:
            SecurityError: If URL scheme is not allowed.
            DownloadError: If download fails.
        """
        from camoufox_mcp.tools.navigation import _validate_url

        _validate_url(url)

        session = self._browser.get_session(session_id)
        session.touch()
        _timeout = timeout or self._browser._settings.default_timeout

        # Derive safe filename
        if not filename:
            parsed_url = urllib.parse.urlparse(url)
            url_filename = Path(parsed_url.path).name or "download"
            filename = _sanitise_filename(url_filename)
        else:
            filename = _sanitise_filename(filename)

        self._download_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._download_dir / filename
        _validate_download_path(output_path, self._download_dir)

        page = await self._browser.get_active_page(session_id)

        try:
            async with page.expect_download(timeout=_timeout) as dl_info:
                await page.goto(url, wait_until="commit", timeout=_timeout)
            download = await dl_info.value
            await download.save_as(str(output_path))

        except (SecurityError, DownloadError, PathTraversalError):
            raise
        except Exception as exc:
            raise DownloadError(
                f"Download from '{url}' failed: {exc}",
                details=str(exc),
            ) from exc

        size = output_path.stat().st_size if output_path.exists() else 0

        logger.info(
            "Download complete",
            extra={
                "session_id": session_id,
                "tool": "browser_download_start",
                "url": url,
                "path": str(output_path),
                "size_bytes": size,
            },
        )

        return {
            "success": True,
            "session_id": session_id,
            "url": url,
            "path": str(output_path),
            "filename": filename,
            "size_bytes": size,
            "message": f"Downloaded '{filename}' ({size} bytes) to '{output_path}'.",
        }

    # ------------------------------------------------------------------ #
    # browser_download_list
    # ------------------------------------------------------------------ #

    async def list_downloads(self) -> dict[str, Any]:
        """
        List files currently in the download directory.

        Returns:
            Dict with success, files (list), count, download_dir.
        """
        self._download_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for f in sorted(self._download_dir.iterdir()):
            if f.is_file():
                files.append(
                    {
                        "filename": f.name,
                        "path": str(f),
                        "size_bytes": f.stat().st_size,
                    }
                )

        return {
            "success": True,
            "count": len(files),
            "files": files,
            "download_dir": str(self._download_dir),
        }

    # ------------------------------------------------------------------ #
    # browser_download_clear
    # ------------------------------------------------------------------ #

    async def clear_downloads(self) -> dict[str, Any]:
        """
        Delete all files in the download directory.

        Returns:
            Dict with success, deleted_count.
        """
        if not self._download_dir.exists():
            return {"success": True, "deleted_count": 0}

        deleted = 0
        for f in self._download_dir.iterdir():
            if f.is_file():
                try:
                    f.unlink()
                    deleted += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Could not delete download file", extra={"file": str(f), "error": str(exc)}
                    )

        logger.info("Downloads cleared", extra={"deleted_count": deleted})
        return {
            "success": True,
            "deleted_count": deleted,
            "message": f"Deleted {deleted} file(s) from download directory.",
        }
