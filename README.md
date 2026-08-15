# KS Discord Bot

PUBG 전적 기반 **전투력(점수) 측정**과 **유튜브 음악 재생**을 지원하는 디스코드 봇입니다.

- 커맨드 접두사: `/` (환경 변수로 변경 가능)
- Python 3.10+ / discord.py 2.x

---

## 1. 기능

| 코그 | 커맨드 | 설명 |
| --- | --- | --- |
| 밸런서 | `/점수 [플레이어명 \| @멘션]` (`실력`, `스탯점수`, `score`) | 최근 매치를 집계해 전투력 점수를 계산합니다. |
| 음악 | `/재생 <링크\|검색어>` (`play`) | 유튜브 음악을 음성 채널에서 재생합니다. |
| 음악 | `/반복`, `/랜덤재생`, `/스킵`, `/정지`, `/일시정지`, `/계속재생`, `/볼륨 <0-100>`, `/대기리스트`, `/강제연결해제` | 재생 제어. |
| 게임 | `/주사위`, `/뽑기`, `/가위바위보 <가위\|바위\|보>`, `/전적` | 간단한 미니 게임. |
| 메시지 | `/숫자`, `/임베드`, `/삭제`, `/수정`, `/따봉`, `/기다리기` | 메시지 관련 예제. |
| 유저관리 | `/추방`, `/차단`, `/차단해제`, `/역할부여` | 관리 권한이 필요한 커맨드. |

> `PUBG_TOKEN`이 없으면 밸런서 코그는 자동으로 비활성화되고, 나머지 기능은 정상 동작합니다.

---

## 2. 빠른 시작

### 2-1. 요구사항

- Python 3.10 이상
- [ffmpeg](https://ffmpeg.org/) (음악 재생에 필요)
- [Poetry](https://python-poetry.org/) (권장) 또는 pip

### 2-2. 설치

```bash
# Poetry 사용 시
poetry install

# 또는 venv + pip
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install "discord.py[voice]" yt-dlp youtube-search-python termcolor aiosqlite aiohttp aiohttp_retry tzdata
```

ffmpeg 설치:

```bash
sudo apt install ffmpeg -y          # Debian/Ubuntu
brew install ffmpeg                 # macOS
winget install Gyan.FFmpeg          # Windows
```

### 2-3. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 만듭니다. (`.env.example` 복사)

```bash
cp .env.example .env
```

```ini
DISCORD_TOKEN=여기에_봇_토큰
PUBG_TOKEN=여기에_PUBG_API_토큰      # 없으면 밸런서 기능만 비활성화됩니다
```

셸 환경 변수로 설정해도 됩니다. (`.env`보다 셸 환경 변수가 우선)

```bash
export DISCORD_TOKEN="your_token_here"
```

### 2-4. 실행

```bash
python -m ks_bot     # 권장
# 또는
python main.py
./run.sh
```

---

## 3. 디스코드 봇 토큰 발급 방법

> 토큰은 **비밀번호와 같습니다.** 절대 깃에 커밋하거나 남에게 공유하지 마세요.
> 노출되었다면 아래 6단계의 `Reset Token`으로 즉시 재발급하세요.

1. **개발자 포털 접속** — <https://discord.com/developers/applications> 에 디스코드 계정으로 로그인합니다.
2. **애플리케이션 생성** — 우측 상단 `New Application` → 이름 입력(예: `KS Bot`) → 약관 동의 → `Create`.
3. **봇 탭 이동** — 왼쪽 메뉴에서 `Bot` 클릭.
4. **특권 인텐트 켜기** — `Privileged Gateway Intents` 항목에서 아래 3개를 **모두 ON** 하고 `Save Changes`.
   - `PRESENCE INTENT` — 멤버가 PUBG를 플레이 중인지 감지하는 데 필요
   - `SERVER MEMBERS INTENT` — 멤버 목록 조회에 필요
   - `MESSAGE CONTENT INTENT` — `/점수` 같은 접두사 커맨드를 읽는 데 **필수**
5. **토큰 발급** — 같은 화면의 `Token` 항목에서 `Reset Token` → `Yes, do it!` → 표시된 토큰을 `Copy`.
   - 토큰은 **이때 한 번만** 전체가 보입니다. 창을 닫으면 다시 볼 수 없고 재발급해야 합니다.
6. **`.env`에 붙여넣기**

   ```ini
   DISCORD_TOKEN=MTIzNDU2Nzg5...(복사한 값)
   ```

### 3-1. 봇을 서버에 초대하기

1. 왼쪽 메뉴 `OAuth2` → `OAuth2 URL Generator`.
2. **SCOPES**에서 `bot` 체크.
3. **BOT PERMISSIONS**에서 최소 아래 항목 체크:
   - `Read Messages/View Channels`, `Send Messages`, `Embed Links`, `Read Message History`, `Add Reactions`, `Manage Messages`
   - 음악 기능: `Connect`, `Speak`
   - 유저관리 커맨드까지 쓸 경우: `Kick Members`, `Ban Members`, `Manage Roles`
4. 화면 아래 `GENERATED URL`을 복사해 브라우저에서 열고, 봇을 넣을 서버를 선택 → `승인`.
5. 서버 멤버 목록에 봇이 보이면 성공입니다.

---

## 4. 채널 ID 확인 방법

디스코드 ID는 기본적으로 숨겨져 있어 **개발자 모드**를 먼저 켜야 합니다.

1. 디스코드 앱에서 좌측 하단 **톱니바퀴(사용자 설정)** 클릭.
2. 왼쪽 메뉴에서 **고급(Advanced)** 선택.
3. **개발자 모드(Developer Mode)** 를 **ON**.
4. 설정을 닫고, ID를 알고 싶은 **텍스트 채널을 우클릭**(모바일은 길게 누르기) → **채널 ID 복사(Copy Channel ID)**.
5. 클립보드에 `1234567890123456789` 형태의 18~19자리 숫자가 복사됩니다. 이것이 채널 ID입니다.

같은 방식으로 서버(길드)를 우클릭하면 **서버 ID 복사**, 유저를 우클릭하면 **사용자 ID 복사**가 가능합니다.

> 웹/데스크톱에서 채널을 열었을 때 주소창의
> `https://discord.com/channels/<서버ID>/<채널ID>` 에서도 확인할 수 있습니다.

### 4-1. 봇으로 특정 채널에 메시지 보내보기 (동작 확인)

레포에 포함된 스크립트로 봇 토큰과 채널 ID가 올바른지 바로 검증할 수 있습니다.

```bash
python scripts/send_message.py --channel-id 1234567890123456789 --message "봇 연결 테스트 ✅"
```

- 토큰은 `DISCORD_TOKEN` 환경 변수(또는 `.env`)에서 읽습니다. `--token`으로 직접 넘길 수도 있습니다.
- 성공하면 해당 채널에 메시지가 올라오고 스크립트는 즉시 종료됩니다.
- `봇이 채널을 볼 수 없습니다` 오류가 나면, 해당 채널의 권한에서 봇 역할에 `채널 보기`/`메시지 보내기`가 있는지 확인하세요.

---

## 5. PUBG API 토큰 발급 방법

1. <https://developer.pubg.com/> 에 접속해 로그인(가입)합니다.
2. 상단 `Apps` → `Create App`.
3. 앱 이름과 설명을 적고, App Type은 `Personal`을 선택한 뒤 생성합니다.
4. 생성된 앱의 `API Key`를 복사해 `.env`의 `PUBG_TOKEN`에 넣습니다.

무료 등급은 **분당 10회** 요청 제한이 있습니다. 봇은 이 제한을 감지해 자동으로 대기/재시도합니다.

---

## 6. 환경 변수

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `DISCORD_TOKEN` | (필수) | 디스코드 봇 토큰 |
| `PUBG_TOKEN` | (없음) | PUBG API 토큰. 없으면 밸런서 코그 비활성화 |
| `PUBG_PLATFORM` | `steam` | PUBG 플랫폼 샤드 |
| `KS_BOT_COMMAND_PREFIX` | `/` | 커맨드 접두사 |
| `KS_BOT_DB_PATH` | `res/history.db` | SQLite DB 경로 |
| `KS_BOT_GAME_RESULT_DIR` | `res/game_result` | 가위바위보 전적 저장 경로 |
| `KS_BOT_LOG_LEVEL` | `INFO` | 로그 레벨 (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `KS_BOT_MEMBER_STATUS_INTERVAL_MINUTES` | `30` | 멤버 플레이 상태 확인 주기(분) |
| `KS_BOT_MAX_MATCH_NUM` | `40` | 점수 계산에 사용할 최근 매치 수 |
| `KS_BOT_PLAYER_CACHE_TTL_HOURS` | `1` | 플레이어 정보 캐시 유효 시간 |

---

## 7. 프로젝트 구조

```
ks_bot/
├── __main__.py         # 엔트리포인트 (python -m ks_bot)
├── bot.py              # KSBot: 코그 자동 로드, 전역 에러 핸들링
├── config.py           # Settings: 환경 변수 로딩/검증 (.env 지원)
├── logging_config.py   # 로깅 설정
├── help_command.py     # 커스텀 도움말
├── common/             # 도메인 공통 계층 (디스코드 비의존)
│   ├── models.py       #   Player / Match / PlayerMatchStats / Stats + API 파싱
│   ├── enums.py        #   GameMode / MatchType / Tier
│   ├── errors.py       #   KSBotError 예외 계층
│   └── timeutil.py     #   타임존 유틸
├── core/               # 인프라/서비스 계층
│   ├── http_client.py  #   ApiClient: 세션 재사용, 재시도, 레이트 리밋
│   ├── repository.py   #   PlayerRepository: SQLite 영속성 + 스키마 마이그레이션
│   ├── pubg.py         #   PubgBalancer: API + 캐시 조합 서비스
│   ├── scoring.py      #   점수 계산 (순수 함수)
│   └── youtube.py      #   유튜브 검색/메타데이터
└── cogs/               # 디스코드 커맨드 (모듈 추가 시 자동 로드)
    ├── balancer.py  game.py  msg.py  music.py  user.py
```

**계층 규칙**: `cogs` → `core` → `common` 방향으로만 의존합니다.
`common`/`core`는 discord.py에 의존하지 않으므로 봇 없이도 테스트할 수 있습니다.

---

## 8. 개발

```bash
pytest                      # 전체 테스트 (네트워크 테스트는 자동 스킵)
pytest -m "not network"     # 네트워크 테스트 명시적 제외
PUBG_TOKEN=... pytest -m network   # 실제 PUBG API 통합 테스트

ruff check .                # 린트
ruff format .               # 포맷
```

- 단위 테스트는 외부 네트워크에 접속하지 않습니다. HTTP 클라이언트 테스트는 로컬 aiohttp 테스트 서버를 띄웁니다.
- `PUBG_TOKEN`이 설정된 경우에만 `network` 마커 테스트가 실행됩니다.

### 새 커맨드 추가하기

`ks_bot/cogs/` 아래에 모듈을 만들고 `setup(bot)` 코루틴만 정의하면 기동 시 자동으로 로드됩니다.

```python
from discord.ext import commands
from ks_bot.bot import KSBot


class MyCog(commands.Cog, name='내코그'):
    def __init__(self, bot: KSBot):
        self.bot = bot

    @commands.command(name='핑')
    async def ping(self, ctx: commands.Context) -> None:
        await ctx.send('퐁!')


async def setup(bot: KSBot) -> None:
    await bot.add_cog(MyCog(bot))
```
