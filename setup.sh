#!/bin/bash
# 개발/실행 환경을 준비한다. (Debian/Ubuntu 기준)
set -euo pipefail

cd "$(dirname "$0")"

echo '==> ffmpeg 설치 (음악 재생에 필요)'
sudo apt install ffmpeg -y

if command -v poetry >/dev/null 2>&1; then
    echo '==> poetry install'
    poetry install
else
    echo '==> poetry가 없어 venv + pip으로 설치합니다.'
    python3 -m venv .venv
    ./.venv/bin/pip install --upgrade pip
    ./.venv/bin/pip install "discord.py[voice]" yt-dlp youtube-search-python termcolor aiosqlite aiohttp aiohttp_retry tzdata
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo '==> .env 파일을 생성했습니다. DISCORD_TOKEN 값을 채워주세요.'
fi

echo '==> 완료. 실행: python -m ks_bot'
