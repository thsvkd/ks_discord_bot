#!/usr/bin/env bash
#
# 이 머신의 디스코드 봇을 컨테이너로 돌린다.
#
# 코레일/클록 봇과 같은 모양이다. 게이트웨이만 붙으므로 호스트에 열 포트는
# 없고, SQLite 는 ./res 에 bind mount 해서 컨테이너를 지워도 전적이 남는다.
# 재부팅하면 restart: unless-stopped 가 다시 올린다.
#
# Usage:
#   scripts/server.sh start [--build] [--foreground]
#   scripts/server.sh stop [--remove]
#   scripts/server.sh restart [--build]
#   scripts/server.sh status
#   scripts/server.sh logs [N] [-f]
#   scripts/server.sh build
#   scripts/server.sh shell
#
# status 는 실행 중이면 0, 아니면 1 을 반환한다.
#   scripts/server.sh status >/dev/null || scripts/server.sh start

# shellcheck source=scripts/_common.sh
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; }

# 토큰이 비어 있으면 compose 가 조용히 떠서 바로 죽는다. 여기서 막는다.
preflight() {
    local token
    require_env_file
    token="$(env_value DISCORD_TOKEN)"
    [[ -n "${token//[$' \t\r\n']/}" ]] || die "DISCORD_TOKEN 이 ${ENV_FILE#"$ROOT_DIR"/} 에 없습니다."
    mkdir -p "$ROOT_DIR/res/game_result"
}

# 호스트에서 직접 띄운 ks-bot 은 같은 토큰으로 게이트웨이를 두고 싸운다.
# 컨테이너를 올리기 전에 그것을 끈다.
stop_host_bot() {
    local pids
    pids="$(pgrep -f '/\.venv/bin/ks-bot$|python -m ks_bot' 2>/dev/null || true)"
    [[ -n "$pids" ]] || return 0
    warn "호스트에서 봇이 돌고 있습니다. 컨테이너로 올리기 전에 종료합니다."
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    local i
    for i in 1 2 3 4 5 6 7 8 9 10; do
        pgrep -f '/\.venv/bin/ks-bot$|python -m ks_bot' >/dev/null 2>&1 || return 0
        sleep 0.5
    done
    pids="$(pgrep -f '/\.venv/bin/ks-bot$|python -m ks_bot' 2>/dev/null || true)"
    # shellcheck disable=SC2086
    [[ -z "$pids" ]] || kill -9 $pids 2>/dev/null || true
}

await_login() {
    local i
    for i in $(seq 1 40); do
        container_running || return 1
        if compose logs --tail 80 app 2>/dev/null | grep -q '로그인 완료'; then
            return 0
        fi
        sleep 1
    done
    # 로그 문구가 바뀌어도, 컨테이너가 살아 있으면 성공으로 본다.
    container_running
}

cmd_start() {
    local build=0 foreground=0 arg
    for arg in "$@"; do
        case "$arg" in
            --build) build=1 ;;
            --foreground|--fg) foreground=1 ;;
            -h|--help) usage; return 0 ;;
            *) die "알 수 없는 옵션: $arg" ;;
        esac
    done

    preflight
    stop_host_bot

    if container_running && (( ! build && ! foreground )); then
        ok "이미 실행 중입니다 (${APP_CONTAINER_NAME})"
        return 0
    fi

    local up=(up)
    (( build )) && up+=(--build)
    if (( foreground )); then
        info "포그라운드로 올립니다 (Ctrl-C 로 중단)"
        compose "${up[@]}"
        return
    fi
    up+=(-d)

    info "컨테이너를 올립니다"
    DOCKER_BUILDKIT=1 compose "${up[@]}"

    if ! await_login; then
        err "컨테이너가 바로 종료됐습니다. 마지막 로그:"
        compose logs --tail 30 app >&2 || true
        die "시작에 실패했습니다."
    fi

    ok "실행 중 (${APP_CONTAINER_NAME})"
    info "상태: $0 status"
    info "로그: $0 logs -f"
    info "중단: $0 stop"
}

cmd_stop() {
    local remove=0 arg
    for arg in "$@"; do
        case "$arg" in
            --remove|--down|--rm) remove=1 ;;
            -h|--help) usage; return 0 ;;
            *) die "알 수 없는 옵션: $arg" ;;
        esac
    done

    require_env_file
    if (( remove )); then
        info "컨테이너와 네트워크를 제거합니다 (데이터는 ./res 에 남습니다)"
        compose down
        ok "제거했습니다."
        return
    fi

    if ! container_exists; then
        info "실행 중인 컨테이너가 없습니다."
        return 0
    fi

    info "컨테이너를 멈춥니다"
    compose stop
    ok "중단했습니다. 전적은 ./res 에 그대로 있습니다."
}

cmd_restart() {
    local build=0 arg
    for arg in "$@"; do
        case "$arg" in
            --build) build=1 ;;
            --foreground|--fg) die "restart 는 항상 백그라운드입니다. 포그라운드는 '$0 start --foreground' 를 쓰세요." ;;
            -h|--help) usage; return 0 ;;
            *) die "알 수 없는 옵션: $arg" ;;
        esac
    done

    preflight
    stop_host_bot

    local up=(up -d --force-recreate)
    (( build )) && up+=(--build)
    info "컨테이너를 다시 만듭니다"
    DOCKER_BUILDKIT=1 compose "${up[@]}"

    if ! await_login; then
        err "컨테이너가 바로 종료됐습니다. 마지막 로그:"
        compose logs --tail 30 app >&2 || true
        die "재시작에 실패했습니다."
    fi
    ok "실행 중 (${APP_CONTAINER_NAME})"
}

cmd_build() {
    require_docker
    info "이미지를 다시 만듭니다"
    DOCKER_BUILDKIT=1 compose build "$@"
    ok "이미지를 만들었습니다 (ksbot:local)"
    container_running && info "적용하려면: $0 restart"
}

cmd_shell() {
    if ! container_running; then
        die "실행 중이 아닙니다."
    fi
    compose exec app bash || compose exec app sh
}

cmd_logs() {
    local lines=40 follow=0 arg
    for arg in "$@"; do
        case "$arg" in
            -f|--follow) follow=1 ;;
            -n) ;;
            [0-9]*) lines="$arg" ;;
            -n*) lines="${arg#-n}" ;;
            -h|--help) usage; return 0 ;;
            *) die "logs: 알 수 없는 옵션 $arg" ;;
        esac
    done

    if ! container_exists; then
        die "컨테이너가 없습니다. 먼저 $0 start 하세요."
    fi

    local args=(logs --tail "$lines")
    (( follow )) && args+=(-f)
    compose "${args[@]}" app
}

cmd_status() {
    local state status running=0

    require_docker
    printf '\n%s\n' "${C_BLUE}── 봇 컨테이너 ${C_RESET}"

    if ! container_exists; then
        err "컨테이너 없음"
        printf '  %-16s %s\n' "이름" "$APP_CONTAINER_NAME"
        printf '  %-16s %s\n' "기동" "$0 start"
        echo
        return 1
    fi

    state="$("${DOCKER[@]}" inspect -f '{{.State.Status}}' "$APP_CONTAINER_NAME" 2>/dev/null || echo unknown)"
    status="$("${DOCKER[@]}" ps -a --filter "name=^${APP_CONTAINER_NAME}$" --format '{{.Status}}' 2>/dev/null || true)"
    if [[ "$state" == "running" ]]; then
        running=1
        ok "실행 중"
    else
        err "실행 중이 아님 (${state})"
    fi
    printf '  %-16s %s\n' "이름" "$APP_CONTAINER_NAME"
    printf '  %-16s %s\n' "상태" "${status:-?}"
    printf '  %-16s %s\n' "이미지" "$("${DOCKER[@]}" inspect -f '{{.Config.Image}}' "$APP_CONTAINER_NAME" 2>/dev/null || echo '?')"
    printf '  %-16s %s\n' "재시작 횟수" "$("${DOCKER[@]}" inspect -f '{{.RestartCount}}' "$APP_CONTAINER_NAME" 2>/dev/null || echo '?')"

    local pid
    pid="$("${DOCKER[@]}" inspect -f '{{.State.Pid}}' "$APP_CONTAINER_NAME" 2>/dev/null || true)"
    if [[ "$running" -eq 1 && "$pid" =~ ^[1-9][0-9]*$ ]]; then
        printf '  %-16s %s\n' "가동" "$(ps -p "$pid" -o etime= 2>/dev/null | tr -d ' ' || echo '?')"
        printf '  %-16s %s\n' "메모리" "$(ps -p "$pid" -o rss= 2>/dev/null | awk '{printf "%.1f MB", $1/1024}' || echo '?')"
    fi

    printf '\n%s\n' "${C_BLUE}── 설정 ${C_RESET}"
    printf '  %-16s %s\n' "설정 원본" "${ENV_FILE#"$ROOT_DIR"/}"
    printf '  %-16s %s\n' "데이터" "${ROOT_DIR}/res"
    printf '  %-16s %s\n' "게이트웨이" "Discord (호스트 포트 없음)"
    (( running )) || printf '  %-16s %s\n' "기동" "$0 start"

    echo
    (( running )) || return 1
}

case "${1:-}" in
    start)   shift; cmd_start "$@" ;;
    stop)    shift; cmd_stop "$@" ;;
    restart) shift; cmd_restart "$@" ;;
    status)  shift; cmd_status "$@" ;;
    logs)    shift; cmd_logs "$@" ;;
    build)   shift; cmd_build "$@" ;;
    shell)   shift; cmd_shell "$@" ;;
    ""|-h|--help|help) usage ;;
    *) err "알 수 없는 명령: $1"; echo; usage; exit 1 ;;
esac
