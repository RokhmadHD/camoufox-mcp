"""
ProfileManager — manages persistent browser profile directories.

A profile is a named subdirectory under CAMOUFOX_PROFILE_DIR.
Each profile stores browser data (cookies, localStorage, cache) independently.

Profile names are validated to prevent path traversal.

Example layout:
    data/profiles/
    ├── default/
    ├── research/
    └── testing/
"""

from __future__ import annotations

import re
from pathlib import Path

from camoufox_mcp.utils.errors import PathTraversalError, SecurityError
from camoufox_mcp.utils.logging import get_logger

logger = get_logger(__name__)

# Only allow alphanumeric, hyphen, underscore — no dots, slashes, spaces
_VALID_PROFILE_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class ProfileManager:
    """
    Manages persistent browser profile directories.

    Profiles live under a configurable root directory.
    The manager validates names and resolves absolute paths safely.
    """

    def __init__(self, profile_root: Path) -> None:
        self._root = profile_root.resolve()

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate_name(self, name: str) -> None:
        """
        Raise SecurityError if the profile name is not safe.

        Args:
            name: Profile name to validate.

        Raises:
            SecurityError: If the name contains disallowed characters.
            PathTraversalError: If resolved path escapes the profile root.
        """
        if not _VALID_PROFILE_NAME.match(name):
            raise SecurityError(
                f"Invalid profile name '{name}'. "
                "Profile names may only contain letters, digits, hyphens, and underscores "
                "(1–64 characters)."
            )
        # Double-check resolved path stays within root
        resolved = (self._root / name).resolve()
        if not str(resolved).startswith(str(self._root)):
            raise PathTraversalError(name)

    # ------------------------------------------------------------------ #
    # Path resolution
    # ------------------------------------------------------------------ #

    def profile_path(self, name: str) -> Path:
        """
        Return the absolute filesystem path for a profile.

        Validates the name before returning.

        Args:
            name: Profile name.

        Returns:
            Absolute Path to the profile directory.
        """
        self.validate_name(name)
        return self._root / name

    def ensure_profile(self, name: str) -> Path:
        """
        Return the profile path, creating the directory if it does not exist.

        Args:
            name: Profile name.

        Returns:
            Absolute Path to the (now-existing) profile directory.
        """
        path = self.profile_path(name)
        path.mkdir(parents=True, exist_ok=True)
        logger.debug("Profile directory ready", extra={"profile": name, "path": str(path)})
        return path

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #

    def list_profiles(self) -> list[str]:
        """
        Return names of all existing profile directories.

        Returns:
            Sorted list of profile names.
        """
        if not self._root.exists():
            return []
        return sorted(
            p.name for p in self._root.iterdir() if p.is_dir() and _VALID_PROFILE_NAME.match(p.name)
        )

    def profile_exists(self, name: str) -> bool:
        """Return True if the profile directory exists on disk."""
        try:
            self.validate_name(name)
        except (SecurityError, PathTraversalError):
            return False
        return (self._root / name).is_dir()

    def delete_profile(self, name: str) -> None:
        """
        Delete a profile directory and all its contents.

        This is destructive — caller must confirm before invoking.

        Args:
            name: Profile name to delete.

        Raises:
            SecurityError: If the name is invalid.
        """
        import shutil

        path = self.profile_path(name)
        if path.exists():
            shutil.rmtree(path)
            logger.info("Profile deleted", extra={"profile": name})
        else:
            logger.debug("Profile delete requested but not found", extra={"profile": name})

    @property
    def root(self) -> Path:
        """The profile root directory."""
        return self._root
