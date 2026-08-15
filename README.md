# KS Discord Bot

PUBG 전적 기반 **전투력(점수) 측정**, **유튜브 음악 재생**, **무료 배포 게임 알림**을 지원하는 디스코드 봇입니다.

- 커맨드 접두사: `/` (환경 변수로 변경 가능)
- Python 3.10+ / discord.py 2.x

---

## 1. 기능

| 코그 | 커맨드 | 설명 |
| --- | --- | --- |
| 밸런서 | `/점수 [플레이어명 \| @멘션]` (`실력`, `스탯점수`, `score`) | 최근 매치를 집계해 전투력 점수를 **0~100** 스케일로 계산합니다. |
| 무료배포 | (자동 알림) / `/무료게임` (`무료배포`, `무료`, `freegames`) | 무료로 풀린 게임을 찾아 채널에 알리고, 진행 중인 목록을 보여줍니다. |
| 음악 | `/재생 <링크\|검색어>` (`play`) | 유튜브 음악을 음성 채널에서 재생합니다. |
| 음악 | `/반복`, `/랜덤재생`, `/스킵`, `/정지`, `/일시정지`, `/계속재생`, `/볼륨 <0-100>`, `/대기리스트`, `/강제연결해제` | 재생 제어. |
| 게임 | `/주사위`, `/뽑기`, `/가위바위보 <가위\|바위\|보>`, `/전적` | 간단한 미니 게임. |
| 메시지 | `/숫자`, `/임베드`, `/삭제`, `/수정`, `/따봉`, `/기다리기` | 메시지 관련 예제. |
| 유저관리 | `/추방`, `/차단`, `/차단해제`, `/역할부여` | 관리 권한이 필요한 커맨드. |

> `PUBG_TOKEN`이 없으면 밸런서 코그가, `KS_BOT_GIVEAWAY_CHANNEL_ID`가 없으면 무료 배포 코그가
> 각각 자동으로 비활성화되고, 나머지 기능은 정상 동작합니다.

`/점수`는 최근 매치(기본 40판)를 **등수·딜량·제압·효율·로비 킬순위**로 채점해 `0~100` 사이의 값을 냅니다.
랭크 매치와 일반 매치를 같은 공식으로 채점하고, 랭크 판 비율만큼 시즌 티어를 섞습니다. 대략적인 기준은
초보 `20`대, 중수 `40` 전후, 고수 `55` 이상, 프로급 `70` 이상입니다. 표본이 적으면 중앙값(`40`) 쪽으로
당겨지므로 판수가 쌓여야 최고 등급이 나옵니다. 자세한 근거는 [`docs/scoring-design.md`](docs/scoring-design.md)에 있습니다.

---

## 2. 빠른 시작

### 2-1. 요구사항

- [uv](https://docs.astral.sh/uv/) — 파이썬 버전과 의존성을 함께 관리합니다
- [ffmpeg](https://ffmpeg.org/) (음악 재생에 필요)

Python은 따로 설치하지 않아도 됩니다. `uv`가 `requires-python`(3.10+)에 맞는 인터프리터를 자동으로 준비합니다.

uv 설치:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # macOS / Linux
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

### 2-2. 설치

```bash
uv sync     # .venv 생성 + uv.lock 기준으로 의존성 설치
```

`setup.sh`를 실행하면 ffmpeg 설치와 `.env` 생성까지 한 번에 처리합니다.

ffmpeg를 직접 설치할 경우:

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
uv run ks-bot        # 권장
# 또는
uv run python -m ks_bot
./run.sh
```

> 가상환경을 직접 활성화했다면(`source .venv/bin/activate`) `python -m ks_bot`으로도 실행됩니다.

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
uv run python scripts/send_message.py --channel-id 1234567890123456789 --message "봇 연결 테스트 ✅"
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
| `KS_BOT_GIVEAWAY_CHANNEL_ID` | (없음) | 무료 배포 알림 채널 ID. 없으면 무료 배포 코그 비활성화 |
| `KS_BOT_GIVEAWAY_INTERVAL_MINUTES` | `30` | 무료 배포 확인 주기(분) |
| `KS_BOT_GIVEAWAY_STORES` | `steam,epic,gog` | 알릴 스토어 목록. `itch`, `ubisoft`, `amazon`, `origin`, `microsoft`, `other` 추가 가능 |
| `KS_BOT_GIVEAWAY_MENTION_ROLE_ID` | (없음) | 알림 시 멘션할 역할 ID |
| `KS_BOT_GIVEAWAY_INCLUDE_UPCOMING` | `true` | 다음 주 예정 배포도 미리 알릴지 |
| `KS_BOT_SLASH_GUILD_ID` | (없음) | 슬래시 커맨드를 즉시 등록할 서버 ID. 없으면 전역 등록(반영까지 최대 1시간) |

---

## 7. 무료 배포 알림은 어떻게 동작하나요

`KS_BOT_GIVEAWAY_CHANNEL_ID`만 채우면 켜집니다. 30분마다 아래 순서로 동작합니다.

```
수집 → 무료 판정 → 실제 스토어 주소 확인 → 한국어 정보 보강 → 중복 제거 → 발행
```

**수집처**는 두 곳입니다.

- **Epic 공식 API** — Epic 배포에 대해 가장 정확합니다. 한국어 제목·설명·원화 가격·정확한 기간이 들어 있습니다.
- **GamerPower** — Steam·GOG·itch 등 나머지 스토어를 넓게 커버합니다.

두 곳 모두 응답이 구조화되어 있어 **별도의 AI 후처리 없이** 필요한 정보가 전부 나옵니다.
부족한 한국어 설명·장르·평점은 Steam `appdetails`로 채웁니다.

주의해서 처리하는 것들:

- Epic의 무료 게임 API는 **단순 할인 예정(20%, 25% 등)도 함께** 돌려줍니다. 할인율이 0%이고
  실제 판매가가 0원인 것만 무료로 인정합니다.
- GamerPower가 주는 링크는 중계 주소라 실제 스토어 주소가 아닙니다. 리다이렉트를 따라가
  상품을 특정하고, 그 결과를 캐시합니다.
- **선착순 키 배포**와 **스토어 전체 무료**를 구분해 표시합니다. 전자는 마감 전에도 끝날 수 있습니다.
- 스토어 무료라고 주장하는 항목은 Steam 가격으로 한 번 더 검증합니다.
- 봇을 **처음 켠 주기**에는 이미 진행 중이던 배포를 발행하지 않고 기록만 남깁니다.
  (채널이 과거 배포로 도배되는 것을 막습니다.)

발행할 때는 건마다 메시지를 나누지 않고 **`지금 받을 수 있는 것`과 `곧 풀리는 것`으로 묶어**
최대 2개의 메시지로 보냅니다. 묶인 카드는 큰 이미지 대신 썸네일을 써서 컴팩트하게 표시되고,
각 게임으로 가는 링크 버튼이 카드 순서대로 붙습니다.

채널을 정하기 전에 결과를 미리 보려면:

```bash
uv run python scripts/preview_giveaways.py --dry-run              # 터미널에 출력만
uv run python scripts/preview_giveaways.py --channel-id <채널ID>  # 실제로 발행해보기
```

(임시 DB를 쓰므로 실제 봇의 발행 이력에는 영향을 주지 않습니다.)

---

## 8. 프로젝트 구조

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
│   ├── giveaway.py     #   Store / ClaimKind / Giveaway + 제목·설명 정리
│   ├── errors.py       #   KSBotError 예외 계층
│   └── timeutil.py     #   타임존 유틸
├── core/               # 인프라/서비스 계층
│   ├── http_client.py  #   ApiClient: 세션 재사용, 재시도, 레이트 리밋, 리다이렉트 해석
│   ├── sqlite.py       #   SqliteRepository: 연결 관리 + 스키마 마이그레이션 공통 기반
│   ├── repository.py   #   PlayerRepository: 플레이어/매치 전적 영속성
│   ├── pubg.py         #   PubgBalancer: API + 캐시 조합 서비스
│   ├── scoring.py      #   점수 계산 (순수 함수)
│   ├── giveaway.py     #   GiveawayService: 무료 배포 수집·정규화·보강
│   ├── giveaway_repository.py  #   발행 이력 + 중계 링크 캐시
│   └── youtube.py      #   유튜브 검색/메타데이터
└── cogs/               # 디스코드 커맨드 (모듈 추가 시 자동 로드)
    ├── balancer.py  game.py  giveaway.py  msg.py  music.py  user.py
```

**계층 규칙**: `cogs` → `core` → `common` 방향으로만 의존합니다.
`common`/`core`는 discord.py에 의존하지 않으므로 봇 없이도 테스트할 수 있습니다.

---

## 9. 개발

```bash
uv run pytest                       # 기본: 외부 네트워크를 타지 않는 테스트만 실행
uv run pytest -m network            # 실제 PUBG API 통합 테스트 (.env의 PUBG_TOKEN 사용)
uv run pytest -m ''                 # 둘 다 실행

uv run ruff check .                 # 린트
uv run ruff format .                # 포맷

uv add <패키지>                      # 의존성 추가 (pyproject + uv.lock 갱신)
uv add --dev <패키지>                # 개발 의존성 추가
uv lock --upgrade                   # 잠긴 버전 일괄 업그레이드
```

`uv.lock`은 저장소에 커밋되어 있으므로, 모든 환경과 CI가 완전히 동일한 버전으로 실행됩니다.

- 단위 테스트는 외부 네트워크에 접속하지 않습니다. HTTP 클라이언트 테스트는 로컬 aiohttp 테스트 서버를 띄웁니다.
- `network` 마커 테스트는 기본 실행에서 제외됩니다. PUBG 무료 등급은 분당 10회 제한이 있어, 다른 테스트와 함께 반복 실행하면 레이트 리밋에 걸립니다.
- `PUBG_TOKEN`이 없으면 `-m network`로 실행해도 자동으로 건너뜁니다.

### 채널 ID를 모를 때

```bash
uv run python scripts/send_message.py --list-channels
```

봇이 속한 서버의 텍스트 채널과 ID, 전송 가능 여부를 표로 보여줍니다.

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
