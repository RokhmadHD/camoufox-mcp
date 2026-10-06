"""
Permission layer for Camoufox MCP.

This module provides a configurable permission model that controls which
operations are allowed for a given session. It is designed to be extended
in Phase 6 with full domain-level and operation-level allow/deny policies.

For Phase 3, it provides:
  - A PermissionSet dataclass describing what a session is allowed to do.
  - A check_permission() function called by services before executing actions.
  - Default permissive settings (all operations allowed) suitable for Phase 3.

Future extensions (Phase 6):
  - Per-session URL allow/deny lists
  - Rate limiting
  - Operation-level disabling (e.g. disable JavaScript execution)
  - Audit logging
"""

from __future__ import annotations

from dataclasses import dataclass, field

from camoufox_mcp.utils.errors import SecurityError

# --------------------------------------------------------------------------- #
# Permission set
# --------------------------------------------------------------------------- #


@dataclass
class PermissionSet:
    """
    Describes what a browser session is permitted to do.

    All flags default to True (permissive) so that Phase 3 works out of the box.
    Phase 6 will add configuration-driven defaults.
    """

    # Navigation
    allow_navigation: bool = True
    allow_back_forward: bool = True
    allow_reload: bool = True

    # Interaction
    allow_click: bool = True
    allow_type: bool = True
    allow_key_press: bool = True
    allow_scroll: bool = True

    # Waiting
    allow_wait: bool = True

    # JavaScript execution (separate flag — higher risk)
    allow_javascript: bool = True

    # Downloads
    allow_downloads: bool = True

    # Screenshots
    allow_screenshots: bool = True

    # URL restrictions (empty = allow all)
    allowed_url_patterns: list[str] = field(default_factory=list)
    blocked_url_patterns: list[str] = field(default_factory=list)


# Default permissive permissions used when no override is configured
DEFAULT_PERMISSIONS = PermissionSet()


# --------------------------------------------------------------------------- #
# Permission registry
# --------------------------------------------------------------------------- #


class PermissionRegistry:
    """
    Maps session IDs to their PermissionSet.

    Unregistered sessions fall back to DEFAULT_PERMISSIONS.
    """

    def __init__(self) -> None:
        self._registry: dict[str, PermissionSet] = {}

    def set_permissions(self, session_id: str, perms: PermissionSet) -> None:
        """Assign a custom PermissionSet to a session."""
        self._registry[session_id] = perms

    def get_permissions(self, session_id: str) -> PermissionSet:
        """Return the PermissionSet for a session (default if not set)."""
        return self._registry.get(session_id, DEFAULT_PERMISSIONS)

    def remove(self, session_id: str) -> None:
        """Remove permissions for a closed session."""
        self._registry.pop(session_id, None)

    def clear(self) -> None:
        """Remove all registered permission sets."""
        self._registry.clear()


# --------------------------------------------------------------------------- #
# Permission check helpers
# --------------------------------------------------------------------------- #


def check_permission(flag: bool, operation: str) -> None:
    """
    Raise SecurityError if a permission flag is False.

    Args:
        flag:      The permission flag (e.g. perms.allow_click).
        operation: Human-readable operation name for the error message.

    Raises:
        SecurityError: If the flag is False.
    """
    if not flag:
        raise SecurityError(
            f"Operation '{operation}' is not permitted for this session. "
            "Contact the server administrator to adjust permissions."
        )


def check_url_permissions(url: str, perms: PermissionSet) -> None:
    """
    Check URL against allowed/blocked pattern lists.

    Patterns use simple substring matching for now.
    Phase 6 will upgrade this to full glob/regex matching.

    Args:
        url:   The URL to check.
        perms: The PermissionSet for the session.

    Raises:
        SecurityError: If the URL matches a blocked pattern or is not in the
                       allowed list (when allowed_url_patterns is non-empty).
    """
    import re as _re

    # Check blocked patterns first
    for pattern in perms.blocked_url_patterns:
        if _re.search(pattern, url):
            raise SecurityError(
                f"URL '{url}' is blocked by the session permission policy "
                f"(matched blocked pattern: '{pattern}')."
            )

    # If allowed list is configured, URL must match at least one
    if perms.allowed_url_patterns:
        for pattern in perms.allowed_url_patterns:
            if _re.search(pattern, url):
                return
        raise SecurityError(f"URL '{url}' is not in the allowed URL list for this session.")
