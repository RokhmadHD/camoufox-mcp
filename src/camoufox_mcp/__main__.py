"""
CLI entry point for Camoufox MCP.

Invoked as:
    camoufox-mcp            # via pyproject.toml [project.scripts]
    python -m camoufox_mcp  # direct module execution

Supports:
    camoufox-mcp --help
    camoufox-mcp --version
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    from camoufox_mcp import __version__

    parser = argparse.ArgumentParser(
        prog="camoufox-mcp",
        description="Camoufox MCP — browser automation server for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  camoufox-mcp                     # start MCP server (stdio transport)
  camoufox-mcp --log-level DEBUG   # verbose logging
  CAMOUFOX_HEADLESS=false camoufox-mcp  # run with visible browser window
""",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Override log level (default: from CAMOUFOX_LOG_LEVEL env var, fallback INFO)",
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        default=False,
        help="Emit logs as JSON (useful for log aggregators)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Main entry point — parse CLI args then run the MCP server."""
    args = _parse_args(argv)

    from camoufox_mcp.config import get_settings

    settings = get_settings()

    # CLI flags override env-based settings
    if args.log_level is not None:
        settings = settings.model_copy(update={"log_level": args.log_level})
    if args.log_json:
        settings = settings.model_copy(update={"log_json": True})

    from camoufox_mcp.server import run

    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(settings))
    sys.exit(0)


if __name__ == "__main__":
    main()
