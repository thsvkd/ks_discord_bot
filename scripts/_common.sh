#!/usr/bin/env bash
# scripts/ 아래에서 source 한다. 직접 실행하지 않는다.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.yml}"
APP_CONTAINER_NAME="${APP_CONTAINER_NAME:-ks_bot}"

if [[ -t 1 ]]; then
    C_RESET=$'\033[0m'
    C_RED=$'\033[31m'
    C_GREEN=$'\033[32m'
    C_YELLOW=$'\033[33m'
    C_BLUE=$'\033[34m'
else
    C_RESET='' C_RED='' C_GREEN='' C_YELLOW='' C_BLUE=''
fi

info() { printf '%s\n' "${C_BLUE}▶${C_RESET} $*"; }
ok()   { printf '%s\n' "${C_GREEN}✔${C_RESET} $*"; }
warn() { printf '%s\n' "${C_YELLOW}⚠${C_RESET} $*" >&2; }
err()  { printf '%s\n' "${C_RED}✖${C_RESET} $*" >&2; }
die()  { err "$*"; exit 1; }

require_env_file() {
    [[ -f "$ENV_FILE" ]] || die "${ENV_FILE#"$ROOT_DIR"/} 이 없습니다. .env.example 을 복사해 토큰을 채우세요."
}

# env_value <KEY> — .env 에서 값을 읽는다. 없으면 빈 문자열.
env_value() {
    local key="$1"
    [[ -f "$ENV_FILE" ]] || return 0
    sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

# docker 소켓 권한이 없는 세션(그룹이 아직 안 붙은 셸)은 sudo 로 우회한다.
resolve_docker() {
    if docker info >/dev/null 2>&1; then
        DOCKER=(docker)
        return 0
    fi
    if sudo -n docker info >/dev/null 2>&1; then
        DOCKER=(sudo -n docker)
        return 0
    fi
    return 1
}

require_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        die "docker 가 설치돼 있지 않습니다."
    fi
    if ! docker compose version >/dev/null 2>&1 && ! command -v docker-compose >/dev/null 2>&1; then
        die "docker compose (v2) 를 찾지 못했습니다."
    fi
    if ! resolve_docker; then
        die "docker 데몬에 접근할 수 없습니다. sudo usermod -aG docker \$USER 후 다시 로그인하거나, sudo 가 비밀번호 없이 docker 를 실행할 수 있어야 합니다."
    fi
}

compose() {
    require_docker
    (cd "$ROOT_DIR" && "${DOCKER[@]}" compose -f "$COMPOSE_FILE" "$@")
}

container_exists() {
    require_docker
    [[ -n "$("${DOCKER[@]}" ps -aq -f "name=^${APP_CONTAINER_NAME}$" 2>/dev/null)" ]]
}

container_running() {
    require_docker
    [[ "$("${DOCKER[@]}" inspect -f '{{.State.Running}}' "$APP_CONTAINER_NAME" 2>/dev/null)" == "true" ]]
}
