#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/../.." && pwd)"

cd "${repo_root}"

require_cmd() {
    local cmd="$1"
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        printf 'missing required command: %s\n' "${cmd}" >&2
        exit 1
    fi
}

require_cmd git
require_cmd make
require_cmd uv

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
    printf 'not inside a git worktree: %s\n' "${repo_root}" >&2
    exit 1
fi

if ! uv python find 3.10 >/dev/null 2>&1; then
    printf 'Installing Python 3.10 via uv...\n'
    uv python install 3.10
fi

make dev-setup
make dev-install

printf '\nBootstrap complete.\n'
printf 'Next step: make check-all\n'
