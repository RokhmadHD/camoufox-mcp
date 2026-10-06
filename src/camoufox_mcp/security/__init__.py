"""Security and permission layer for Camoufox MCP."""

from camoufox_mcp.security.permissions import (
    DEFAULT_PERMISSIONS,
    PermissionRegistry,
    PermissionSet,
    check_permission,
    check_url_permissions,
)
from camoufox_mcp.security.validation import (
    ParsedSelector,
    parse_selector,
    validate_key,
    validate_scroll,
    validate_text_input,
)

__all__ = [
    "DEFAULT_PERMISSIONS",
    "PermissionRegistry",
    "PermissionSet",
    "check_permission",
    "check_url_permissions",
    "ParsedSelector",
    "parse_selector",
    "validate_key",
    "validate_scroll",
    "validate_text_input",
]
