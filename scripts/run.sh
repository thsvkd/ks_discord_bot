#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v uv >/dev/null 2>&1; then
    exec uv run ks-bot
fi

# uv가 없으면 현재 파이썬 환경으로 실행한다.
exec python -m ks_bot
