#!/bin/bash
# 개발/실행 환경을 준비한다. (Debian/Ubuntu 기준)
set -euo pipefail

cd "$(dirname "$0")/.."

echo '==> ffmpeg 설치 (음악 재생에 필요)'
if command -v apt >/dev/null 2>&1; then
    sudo apt install ffmpeg -y
else
    echo '   apt가 없어 건너뜁니다. ffmpeg를 직접 설치해주세요.'
fi

if ! command -v uv >/dev/null 2>&1; then
    echo '==> uv 설치'
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo '==> uv sync (가상환경 + 의존성 설치)'
uv sync

if [ ! -f .env ]; then
    cp .env.example .env
    echo '==> .env 파일을 생성했습니다. DISCORD_TOKEN 값을 채워주세요.'
fi

echo '==> 완료. 실행: uv run ks-bot  또는  ./scripts/run.sh'
