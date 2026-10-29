#!/usr/bin/env bash
# One-shot setup for Semantiks CUA. Idempotent: safe to rerun.
#
# Installs:
#   - uv (via Homebrew/curl, if missing)
#   - trycua/cua Driver (cross-OS native binary)
#   - Python deps + the `semantiks-cua` command
#
# After this runs, you can just type `semantiks-cua` from anywhere.

set -euo pipefail
cd "$(dirname "$0")"

say() { printf "\033[1;36m→\033[0m %s\n" "$*"; }
ok()  { printf "\033[1;32m✓\033[0m %s\n" "$*"; }
err() { printf "\033[1;31m✗\033[0m %s\n" "$*" >&2; }

# --- uv ---------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  err "uv is not installed."
  echo "   Install one of these ways, then re-run ./setup.sh:"
  echo "     brew install uv"
  echo "     curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi
ok "uv found ($(uv --version))"

# --- cua Driver -------------------------------------------------------------
if ! command -v cua-driver >/dev/null 2>&1; then
  say "installing trycua/cua Driver (cross-OS native binary)…"
  /bin/bash -c "$(curl -fsSL https://cua.ai/driver/install.sh)"
  ok "cua Driver installed"
else
  ok "cua Driver already present ($(cua-driver --version 2>/dev/null || echo installed))"
fi

say "granting cua Driver OS permissions (follow the prompts if asked)…"
cua-driver permissions grant || true

# --- venv + deps ------------------------------------------------------------
if [ -d .venv ]; then
  ok "existing .venv — reusing"
else
  say "creating .venv (Python >=3.11)…"
  uv venv --python ">=3.11"
fi

say "installing Python deps + the semantiks-cua command…"
uv pip install -e .
ok "dependencies installed"

# --- .env -------------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  ok "created .env from .env.example"
  cat <<'EOF'

┌── NEXT STEP ─────────────────────────────────────────────────────┐
│  Edit .env and set OPENAI_API_KEY with access to gpt-6.1-sol.    │
│  Optional: LANGSMITH_* for traces, POSTHOG_API_KEY for events.   │
│                                                                  │
│  Then run:  semantiks-cua                                        │
└──────────────────────────────────────────────────────────────────┘
EOF
else
  ok ".env already exists — not touching it"
fi

echo
ok "setup complete. Next:  source .venv/bin/activate && semantiks-cua"
