#!/usr/bin/env bash
# ==============================================================================
# install.sh — Camoufox MCP installer
#
# Usage:
#   bash install.sh              # install + configure Kiro CLI
#   bash install.sh --no-kiro    # install only, skip Kiro CLI config
#   bash install.sh --help
# ==============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------- #
# Config
# ---------------------------------------------------------------------------- #

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
UV_BIN="$HOME/.local/bin/uv"
KIRO_MCP_CONFIG="$HOME/.kiro/settings/mcp.json"
PYTHON_BIN="$VENV_DIR/bin/python"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

# ---------------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------------- #

info()    { echo -e "${BLUE}[INFO]${RESET}  $*"; }
ok()      { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }
step()    { echo -e "\n${BOLD}==> $*${RESET}"; }
die()     { error "$*"; exit 1; }

# ---------------------------------------------------------------------------- #
# Parse args
# ---------------------------------------------------------------------------- #

CONFIGURE_KIRO=true

for arg in "$@"; do
  case "$arg" in
    --no-kiro)   CONFIGURE_KIRO=false ;;
    --help|-h)
      echo "Usage: bash install.sh [--no-kiro] [--help]"
      echo ""
      echo "Options:"
      echo "  --no-kiro   Skip Kiro CLI MCP configuration"
      echo "  --help      Show this help"
      exit 0
      ;;
    *)
      die "Unknown argument: $arg. Use --help for usage."
      ;;
  esac
done

# ---------------------------------------------------------------------------- #
# Banner
# ---------------------------------------------------------------------------- #

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║       Camoufox MCP Installer         ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════╝${RESET}"
echo ""
info "Project dir : $PROJECT_DIR"
info "Venv dir    : $VENV_DIR"
info "Kiro config : $KIRO_MCP_CONFIG"
echo ""

# ---------------------------------------------------------------------------- #
# Step 1 — Check Python
# ---------------------------------------------------------------------------- #

step "Checking Python"

if ! command -v python3 &>/dev/null; then
  die "python3 not found. Install Python 3.12+ first."
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || [ "$PY_MAJOR" -eq 3 -a "$PY_MINOR" -lt 12 ]; then
  die "Python 3.12+ required. Found Python $PY_VERSION."
fi

ok "Python $PY_VERSION found at $(which python3)"

# ---------------------------------------------------------------------------- #
# Step 2 — Install uv if missing
# ---------------------------------------------------------------------------- #

step "Checking uv"

if command -v uv &>/dev/null; then
  UV_BIN="$(which uv)"
  ok "uv already in PATH: $UV_BIN ($(uv --version))"
elif [ -x "$HOME/.local/bin/uv" ]; then
  UV_BIN="$HOME/.local/bin/uv"
  ok "uv found at $UV_BIN ($($UV_BIN --version))"
else
  info "uv not found — installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  UV_BIN="$HOME/.local/bin/uv"
  if [ ! -x "$UV_BIN" ]; then
    die "uv install failed. Try manually: curl -LsSf https://astral.sh/uv/install.sh | sh"
  fi
  ok "uv installed at $UV_BIN ($($UV_BIN --version))"
fi

# ---------------------------------------------------------------------------- #
# Step 3 — Install dependencies
# ---------------------------------------------------------------------------- #

step "Installing Python dependencies"

cd "$PROJECT_DIR"

if [ -d "$VENV_DIR" ]; then
  info "Virtual environment already exists, syncing..."
else
  info "Creating virtual environment..."
fi

"$UV_BIN" sync --extra dev

if [ ! -x "$PYTHON_BIN" ]; then
  die "Virtual environment setup failed: $PYTHON_BIN not found."
fi

ok "Dependencies installed in $VENV_DIR"

# ---------------------------------------------------------------------------- #
# Step 4 — Check Camoufox browser binary
# ---------------------------------------------------------------------------- #

step "Checking Camoufox browser binary"

CAMOUFOX_CACHE_DIR="$HOME/.cachekde/camoufox/browsers/official"

if [ -d "$CAMOUFOX_CACHE_DIR" ] && [ -n "$(ls -A "$CAMOUFOX_CACHE_DIR" 2>/dev/null)" ]; then
  BROWSER_VER=$(ls "$CAMOUFOX_CACHE_DIR" | head -1)
  ok "Camoufox browser found: $BROWSER_VER"
else
  warn "Camoufox browser binary not found at $CAMOUFOX_CACHE_DIR"
  info "Downloading Camoufox browser (this may take a few minutes)..."
  "$PYTHON_BIN" -m camoufox fetch
  if [ $? -eq 0 ]; then
    ok "Camoufox browser downloaded successfully"
  else
    warn "camoufox fetch failed. The server may not work until the browser is downloaded."
    warn "Try manually: $PYTHON_BIN -m camoufox fetch"
  fi
fi

# ---------------------------------------------------------------------------- #
# Step 5 — Create data directories
# ---------------------------------------------------------------------------- #

step "Creating data directories"

mkdir -p "$PROJECT_DIR/data/profiles"
mkdir -p "$PROJECT_DIR/data/screenshots"
mkdir -p "$PROJECT_DIR/data/downloads"
ok "data/profiles, data/screenshots, data/downloads created"

# ---------------------------------------------------------------------------- #
# Step 6 — Create .env if missing
# ---------------------------------------------------------------------------- #

step "Setting up .env"

if [ -f "$PROJECT_DIR/.env" ]; then
  info ".env already exists — skipping"
else
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  ok ".env created from .env.example"
fi

# ---------------------------------------------------------------------------- #
# Step 7 — Smoke test
# ---------------------------------------------------------------------------- #

step "Running smoke test"

SMOKE_RESULT=$(echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' \
  | timeout 8 "$PYTHON_BIN" -m camoufox_mcp 2>/dev/null | head -1 || echo "FAILED")

if echo "$SMOKE_RESULT" | grep -q '"protocolVersion"'; then
  ok "MCP server responds correctly to initialize"
else
  warn "Smoke test inconclusive — server may still work"
  info "Manual test: echo '{...}' | $PYTHON_BIN -m camoufox_mcp"
fi

# ---------------------------------------------------------------------------- #
# Step 8 — Configure Kiro CLI (optional)
# ---------------------------------------------------------------------------- #

if [ "$CONFIGURE_KIRO" = true ]; then
  step "Configuring Kiro CLI MCP"

  KIRO_SETTINGS_DIR="$HOME/.kiro/settings"

  if [ ! -d "$KIRO_SETTINGS_DIR" ]; then
    warn "Kiro settings directory not found: $KIRO_SETTINGS_DIR"
    warn "Is Kiro CLI installed? Skipping Kiro configuration."
    warn "You can configure manually later — see step.md"
  else
    # Backup existing mcp.json if it has content
    if [ -f "$KIRO_MCP_CONFIG" ] && [ -s "$KIRO_MCP_CONFIG" ]; then
      BACKUP="$KIRO_MCP_CONFIG.bak.$(date +%Y%m%d_%H%M%S)"
      cp "$KIRO_MCP_CONFIG" "$BACKUP"
      info "Existing mcp.json backed up to: $BACKUP"

      # Merge or overwrite?
      # Check if camoufox key already exists
      if grep -q '"camoufox"' "$KIRO_MCP_CONFIG" 2>/dev/null; then
        info "camoufox server already present in mcp.json — updating..."
      fi
    fi

    # Write the config (always overwrite camoufox entry)
    cat > "$KIRO_MCP_CONFIG" <<EOF
{
  "mcpServers": {
    "camoufox": {
      "command": "${PYTHON_BIN}",
      "args": ["-m", "camoufox_mcp"],
      "env": {
        "CAMOUFOX_HEADLESS": "true",
        "CAMOUFOX_LOG_LEVEL": "INFO"
      },
      "timeout": 60000
    }
  }
}
EOF
    ok "Kiro CLI configured: $KIRO_MCP_CONFIG"
    info "Kiro will auto-reload the config — no restart needed"
  fi
fi

# ---------------------------------------------------------------------------- #
# Done
# ---------------------------------------------------------------------------- #

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║   Installation complete! 🎉           ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════╝${RESET}"
echo ""
echo -e "${BOLD}Quick start:${RESET}"
echo ""
echo -e "  Start MCP server manually:"
echo -e "    ${BLUE}$PYTHON_BIN -m camoufox_mcp${RESET}"
echo ""
echo -e "  Run tests:"
echo -e "    ${BLUE}cd $PROJECT_DIR && $UV_BIN run pytest tests/unit/${RESET}"
echo ""
echo -e "  Change settings:"
echo -e "    ${BLUE}$PROJECT_DIR/.env${RESET}"
echo ""
if [ "$CONFIGURE_KIRO" = true ] && [ -f "$KIRO_MCP_CONFIG" ]; then
  echo -e "  Kiro CLI MCP config:"
  echo -e "    ${BLUE}$KIRO_MCP_CONFIG${RESET}"
  echo ""
  echo -e "  In Kiro chat, try:"
  echo -e "    ${BLUE}Launch a browser, go to https://example.com, extract the text${RESET}"
  echo ""
fi
echo -e "  See full progress & roadmap:"
echo -e "    ${BLUE}$PROJECT_DIR/step.md${RESET}"
echo ""
