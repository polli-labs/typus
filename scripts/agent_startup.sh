#!/usr/bin/env bash
# codex_setup.sh – run inside the Codex “setup script” field
# Assumes an Ubuntu-based container with Python ≥3.10 and internet *during setup* only.
### REVIEW: add sqlite3? to inspect generated test fixture?

set -euo pipefail

# 1. System libs needed for wheels (optional here, but harmless)
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y git build-essential

# 2. Virtualenv
python -m venv .venv
source .venv/bin/activate

# 3. Fast resolver + install dev extras & SQLite driver (offline tests)
python -m pip install -U pip uv
uv pip install -e ".[dev,sqlite]"  # ← pulls pytest, pytest-asyncio, ruff, aiosqlite

echo "✅ Typus dev environment ready (SQLite fixture; no external DB)."