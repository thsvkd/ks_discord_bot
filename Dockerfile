# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.9

# --------------------------------------------------------------------- build
FROM ghcr.io/astral-sh/uv:${UV_VERSION}-python${PYTHON_VERSION}-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# 서드파티 의존성만 먼저 받는 레이어. 봇 코드를 고쳐도 이 레이어는 다시 받지 않는다.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-editable --no-install-project

COPY pyproject.toml uv.lock README.md ./
COPY ks_bot/ ./ks_bot/

# --no-editable 은 패키지를 site-packages 로 복사한다. 런타임 스테이지는
# 가상환경만 있으면 되고, 소스 트리를 이미지에 남기지 않는다.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ------------------------------------------------------------------- runtime
FROM python:${PYTHON_VERSION}-slim AS runtime

# uid/gid 1000 은 이 Pi 의 운영 계정(pi)과 같다. res/ 를 bind mount 하므로
# 숫자가 어긋나면 SQLite 를 열지 못해 기동 직후 죽는다.
RUN groupadd --system --gid 1000 app \
 && useradd --system --uid 1000 --gid app --no-create-home app \
 && apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libopus0 \
 && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    KS_BOT_DB_PATH=/app/res/history.db \
    KS_BOT_GAME_RESULT_DIR=/app/res/game_result

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv

RUN mkdir -p /app/res /app/res/game_result && chown -R app:app /app/res

USER app

# 배열 형식이라 셸을 거치지 않고 PID 1 이 봇이 된다.
# docker stop 의 SIGTERM 이 KeyboardInterrupt 로 이어져 정리하고 끝난다.
CMD ["python", "-m", "ks_bot"]
