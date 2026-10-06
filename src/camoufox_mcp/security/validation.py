"""
Input validation for selectors, text input, key names, and scroll values.

This module is the single point of truth for what is and is not acceptable
input before it reaches the browser. It never touches the browser itself —
it only validates strings and numbers.

Selector format supported:
    css=.my-class          → Playwright CSS
    xpath=//div[@id='x']   → Playwright XPath
    text=Submit            → Playwright text selector
    role=button            → Playwright ARIA role
    label=Email            → Playwright label selector
    placeholder=Search     → Playwright placeholder
    #my-id                 → shorthand CSS (no prefix)
    .my-class              → shorthand CSS (no prefix)
"""

from __future__ import annotations

import re
from typing import Final

from camoufox_mcp.utils.errors import SecurityError, SelectorError

# --------------------------------------------------------------------------- #
# Selector prefixes
# --------------------------------------------------------------------------- #

# Recognised selector type prefixes (lowercase)
SELECTOR_PREFIXES: Final[frozenset[str]] = frozenset(
    {"css", "xpath", "text", "role", "label", "placeholder", "id", "testid"}
)

# Maximum selector string length — prevents absurdly long inputs
MAX_SELECTOR_LENGTH: Final[int] = 1024

# Maximum text input length per type call
MAX_TYPE_LENGTH: Final[int] = 10_000

# Maximum scroll delta (pixels) per call
MAX_SCROLL_DELTA: Final[int] = 50_000

# Playwright key names reference: https://playwright.dev/docs/api/class-keyboard
# We allow any single printable character, or any of these named keys.
_NAMED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "Backspace",
        "Tab",
        "Delete",
        "Escape",
        "ArrowDown",
        "End",
        "Enter",
        "Home",
        "Insert",
        "PageDown",
        "PageUp",
        "ArrowRight",
        "ArrowUp",
        "ArrowLeft",
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
        "F6",
        "F7",
        "F8",
        "F9",
        "F10",
        "F11",
        "F12",
        "Shift",
        "Control",
        "Alt",
        "Meta",
        "CapsLock",
        "NumLock",
        "Pause",
        "PrintScreen",
        "ScrollLock",
        "Space",
        " ",
    }
)

# Combination key pattern: e.g. "Control+c", "Shift+Enter", "Meta+a"
_COMBO_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(r"^(Shift|Control|Alt|Meta)\+(.+)$")


# --------------------------------------------------------------------------- #
# Selector validation
# --------------------------------------------------------------------------- #


class ParsedSelector:
    """The result of parsing and validating a raw selector string."""

    __slots__ = ("selector_type", "value", "playwright_selector")

    def __init__(self, selector_type: str, value: str, playwright_selector: str) -> None:
        self.selector_type = selector_type
        self.value = value
        self.playwright_selector = playwright_selector

    def __repr__(self) -> str:
        return (
            f"ParsedSelector(type={self.selector_type!r}, playwright={self.playwright_selector!r})"
        )


def parse_selector(raw: str) -> ParsedSelector:
    """
    Parse and validate a raw selector string.

    Supports:
        css=<expr>           Playwright CSS locator
        xpath=<expr>         Playwright XPath locator
        text=<expr>          Playwright text locator
        role=<name>          Playwright ARIA role locator
        label=<text>         Playwright label locator
        placeholder=<text>   Playwright placeholder locator
        #id                  Shorthand → css=#id
        .class               Shorthand → css=.class
        <bare-css>           Any other string → css=<expr>

    Args:
        raw: The raw selector string from the MCP tool call.

    Returns:
        A ParsedSelector with the Playwright-compatible selector string.

    Raises:
        SelectorError: If the selector is empty, too long, or has invalid format.
    """
    if not raw or not isinstance(raw, str):
        raise SelectorError("<empty>", "Selector must be a non-empty string")

    raw = raw.strip()

    if len(raw) > MAX_SELECTOR_LENGTH:
        raise SelectorError(
            raw[:60] + "...",
            f"Selector is too long ({len(raw)} chars, max {MAX_SELECTOR_LENGTH})",
        )

    # Check for explicit prefix like "css=", "xpath=", etc.
    if "=" in raw:
        prefix, _, remainder = raw.partition("=")
        prefix_lower = prefix.lower().strip()
        if prefix_lower in SELECTOR_PREFIXES:
            if not remainder.strip():
                raise SelectorError(
                    raw,
                    f"Selector value after '{prefix}=' must not be empty",
                )
            playwright_selector = _build_playwright_selector(prefix_lower, remainder)
            return ParsedSelector(
                selector_type=prefix_lower,
                value=remainder,
                playwright_selector=playwright_selector,
            )

    # Shorthand: #id or .class → treat as CSS
    if raw.startswith(("#", ".")):
        return ParsedSelector(
            selector_type="css",
            value=raw,
            playwright_selector=raw,
        )

    # Fallback: treat as CSS
    return ParsedSelector(
        selector_type="css",
        value=raw,
        playwright_selector=raw,
    )


def _build_playwright_selector(prefix: str, value: str) -> str:
    """Convert a prefix+value pair into a Playwright locator string."""
    match prefix:
        case "css":
            return value
        case "xpath":
            return f"xpath={value}"
        case "text":
            return f"text={value}"
        case "role":
            return f"role={value}"
        case "label":
            return f"label={value}"
        case "placeholder":
            return f"placeholder={value}"
        case "id":
            return f"#{value}"
        case "testid":
            return f"data-testid={value}"
        case _:
            return value


# --------------------------------------------------------------------------- #
# Text input validation
# --------------------------------------------------------------------------- #


def validate_text_input(text: str) -> str:
    """
    Validate text to be typed into a browser element.

    Args:
        text: The text string from the MCP tool call.

    Returns:
        The validated (stripped of null bytes) text string.

    Raises:
        SecurityError: If text is empty or exceeds max length.
    """
    if not isinstance(text, str):
        raise SecurityError("Type text must be a string.")
    if len(text) == 0:
        raise SecurityError("Type text must not be empty.")
    if len(text) > MAX_TYPE_LENGTH:
        raise SecurityError(
            f"Type text is too long ({len(text)} chars, max {MAX_TYPE_LENGTH}). "
            "Split into multiple calls if needed."
        )
    # Strip null bytes — these can cause issues in some browser contexts
    return text.replace("\x00", "")


# --------------------------------------------------------------------------- #
# Key press validation
# --------------------------------------------------------------------------- #


def validate_key(key: str) -> str:
    """
    Validate a keyboard key name for browser_press.

    Accepts:
        - Single printable characters: "a", "1", "!", etc.
        - Named keys: "Enter", "Escape", "ArrowDown", etc.
        - Modifier combinations: "Control+c", "Shift+Enter", etc.

    Args:
        key: The key name string.

    Returns:
        The validated key string (unchanged).

    Raises:
        SecurityError: If the key name is not recognised.
    """
    if not key or not isinstance(key, str):
        raise SecurityError("Key must be a non-empty string.")

    # Only strip if the key is not a lone space (space is a valid key)
    if key != " ":
        key = key.strip()

    if not key:
        raise SecurityError("Key must be a non-empty string.")

    # Single printable character (including space)
    if len(key) == 1:
        return key

    # Named key
    if key in _NAMED_KEYS:
        return key

    # Modifier combination: e.g. "Control+c"
    m = _COMBO_KEY_PATTERN.match(key)
    if m:
        sub_key = m.group(2)
        # sub_key must be a single char or a named key
        if len(sub_key) == 1 or sub_key in _NAMED_KEYS:
            return key
        raise SecurityError(
            f"Unknown sub-key '{sub_key}' in combination '{key}'. "
            "Use a single character or a named key."
        )

    raise SecurityError(
        f"Unknown key '{key}'. "
        "Use a single character (e.g. 'a'), a named key (e.g. 'Enter', 'Escape'), "
        "or a modifier combination (e.g. 'Control+c')."
    )


# --------------------------------------------------------------------------- #
# Scroll validation
# --------------------------------------------------------------------------- #


def validate_scroll(x: int | float, y: int | float) -> tuple[int, int]:
    """
    Validate scroll delta values.

    Args:
        x: Horizontal scroll delta in pixels.
        y: Vertical scroll delta in pixels.

    Returns:
        A (x, y) tuple of integers.

    Raises:
        SecurityError: If values are out of range or not numeric.
    """
    try:
        xi, yi = int(x), int(y)
    except (TypeError, ValueError) as exc:
        raise SecurityError(f"Scroll deltas must be integers, got x={x!r}, y={y!r}") from exc

    if abs(xi) > MAX_SCROLL_DELTA or abs(yi) > MAX_SCROLL_DELTA:
        raise SecurityError(
            f"Scroll delta ({xi}, {yi}) exceeds maximum allowed value of "
            f"±{MAX_SCROLL_DELTA} pixels per call."
        )
    return xi, yi
