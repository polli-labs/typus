#!/usr/bin/env bash
# codex_setup.sh – executed once in the sandbox build image

set -euo pipefail

# ---- 1. system libs ---------------------------------------------------------
apt-get update -qq
DEBIAN_FRONTEND=noninteractive \
  apt-get install -y --no-install-recommends \
    git build-essential libpq-dev curl

# ---- 2. Python venv ---------------------------------------------------------
python -m venv .venv
source .venv/bin/activate

# ---- 3. Fast resolver + project install ------------------------------------
python -m pip install -U pip uv

# install full dev + sqlite + parquet/arrow + asset helpers
uv pip install -e ".[dev,sqlite,parquet,assets, docs]"   # add ,docs if you need mkdocs in CI

echo "✅  Typus sandbox ready: dev + sqlite + parquet/arrow extras installed."