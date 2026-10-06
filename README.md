# Camoufox MCP

> Browser automation server for AI agents — powered by [Camoufox](https://camoufox.com) and the [Model Context Protocol](https://modelcontextprotocol.io).

---

## What is Camoufox MCP?

Camoufox MCP is a production-ready MCP server that exposes browser automation capabilities to AI agents. It wraps [Camoufox](https://camoufox.com/python) (a privacy-focused Firefox fork built on Playwright) behind a clean, modular API designed for agent workflows.

**It is not a thin Playwright wrapper.**  
It is a structured browser runtime with session management, profile isolation, a security layer, and an extraction engine — all accessible through MCP tools.

---

## Features

- **Session management** — multiple independent browser sessions with unique IDs
- **Profile system** — persistent browser profiles with per-profile configuration
- **Navigation** — goto, back, forward, reload with proper wait strategies
- **Interaction** — click, type, press, scroll with semantic selector support
- **Extraction** — structured text, HTML, links, and metadata extraction
- **Screenshots** — full-page, viewport, or element-level screenshots
- **JavaScript execution** — sandboxed `browser_eval` tool
- **Tab management** — open, close, switch between tabs
- **Download management** — controlled file downloads with path safety
- **Security layer** — permission model and URL/path validation
- **Structured logging** — session-level traceability, plain-text and JSON modes
- **Graceful shutdown** — no orphaned browser processes

---

## Architecture

```text
AI Client
   │ MCP (stdio)
   ▼
Camoufox MCP Server
   ├── Tool Registry
   ├── BrowserManager  ──► Camoufox (AsyncCamoufox)
   ├── SessionManager
   ├── ExtractionEngine
   ├── DownloadManager
   └── Security / Permission Layer
```

Each MCP tool follows the pattern:

```
MCP Tool → Service → Manager → Camoufox Adapter → Browser
```

---

## Installation

### With uv (recommended)

```bash
git clone https://github.com/camoufox-mcp/camoufox-mcp
cd camoufox-mcp
uv sync
```

### From PyPI (once published)

```bash
uv tool install camoufox-mcp
```

---

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env

# 2. Start the MCP server
camoufox-mcp

# or with uv
uv run camoufox-mcp
```

---

## MCP Configuration

Add to your MCP client config (e.g. Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "camoufox": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/camoufox-mcp", "camoufox-mcp"]
    }
  }
}
```

---

## Available Tools (Phase 1)

| Tool | Description |
|---|---|
| `browser_launch` | Launch a new browser session |
| `browser_close` | Close an existing session |
| `browser_sessions` | List active sessions |

More tools are added in subsequent phases — see [docs/tools.md](docs/tools.md).

---

## Configuration

All settings are controlled via environment variables.  
See [`.env.example`](.env.example) and [docs/configuration.md](docs/configuration.md).

---

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Lint
uv run ruff check src/

# Format
uv run ruff format src/

# Tests
uv run pytest
```

---

## Docker

```bash
docker build -t camoufox-mcp .
docker run --rm -i camoufox-mcp
```

See [Dockerfile](Dockerfile) for configuration options.

---

## Security

This project is designed for legitimate browser automation, testing, research, and accessibility workflows. See [docs/security.md](docs/security.md) for the full security model.

---

## Roadmap

- [ ] Phase 2: Navigation, tabs, session persistence
- [ ] Phase 3: Click, type, press, scroll, wait
- [ ] Phase 4: Extraction engine (text, HTML, links, structured data)
- [ ] Phase 5: Screenshots, downloads
- [ ] Phase 6: Security / permission layer
- [ ] Phase 7: Unit + integration tests
- [ ] Phase 8: Full documentation
- [ ] Phase 9: PyPI release, Docker image

---

## License

MIT — see [LICENSE](LICENSE).
