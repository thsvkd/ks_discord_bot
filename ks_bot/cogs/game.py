"""주사위/뽑기/가위바위보 등 간단한 게임 코그."""

from __future__ import annotations

import asyncio
import random
import re
from pathlib import Path

from discord.ext import commands

from ks_bot.bot import KSBot
from ks_bot.logging_config import get_logger

logger = get_logger(__name__)

RPS_CHOICES = ('가위', '바위', '보')
MINERALS = ('다이아몬드', '루비', '에메랄드', '자수정', '철', '석탄')
MINERAL_WEIGHTS = (1, 3, 6, 15, 25, 50)
MAX_RESULT_CHARS = 1800  # 디스코드 메시지 길이(2000자) 여유분

_UNSAFE_FILENAME_CHARS = re.compile(r'[^\w.\-가-힣]+')


def safe_file_name(user_name: str) -> str:
    """사용자 이름을 파일명으로 안전하게 바꾼다(경로 탈출 방지)."""
    cleaned = _UNSAFE_FILENAME_CHARS.sub('_', user_name).strip('._')
    return f'{cleaned or "unknown"}.txt'


def judge_rps(user_choice: str, bot_choice: str) -> str:
    """가위바위보 결과를 'win' | 'lose' | 'draw'로 판정한다."""
    diff = (RPS_CHOICES.index(user_choice) - RPS_CHOICES.index(bot_choice)) % 3
    return {0: 'draw', 1: 'win', 2: 'lose'}[diff]


class Game(commands.Cog, name='게임'):
    """간단한 미니 게임 모음."""

    def __init__(self, bot: KSBot):
        self.bot = bot
        self.result_dir: Path = Path(bot.settings.game_result_dir)

    def _result_path(self, user_name: str) -> Path:
        return self.result_dir / safe_file_name(user_name)

    def _append_result_sync(self, path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as f:
            f.write(line)

    async def append_result(self, user_name: str, line: str) -> None:
        """전적을 파일에 비동기로 추가한다(블로킹 IO는 스레드에서 처리)."""
        await asyncio.to_thread(self._append_result_sync, self._result_path(user_name), line)

    async def read_result(self, user_name: str) -> str:
        path = self._result_path(user_name)
        if not path.is_file():
            return ''
        return await asyncio.to_thread(path.read_text, 'utf-8')

    @commands.hybrid_group(
        name='게임',
        help='주사위/뽑기/가위바위보 등 미니 게임 커맨드입니다.',
        description='주사위/뽑기/가위바위보 등 미니 게임 커맨드입니다.',
        invoke_without_command=True,
    )
    async def game_group(self, ctx: commands.Context) -> None:
        """`/게임`만 입력했을 때 하위 커맨드를 안내한다.

        슬래시로는 그룹 자체를 호출할 수 없으므로(디스코드 제약) 이 콜백은 접두사 전용이다.
        """
        await ctx.send_help(ctx.command)

    @game_group.command(name='주사위', help='주사위를 굴립니다.')
    async def dice(self, ctx: commands.Context) -> None:
        await ctx.send(f'주사위 결과는 {random.randint(1, 6)} 입니다.')

    @game_group.command(name='뽑기', help='뽑기를 합니다.')
    async def mining(self, ctx: commands.Context) -> None:
        results = random.choices(MINERALS, weights=MINERAL_WEIGHTS, k=5)
        await ctx.send(f'{", ".join(results)} 광물들을 획득하였습니다.')

    @game_group.command(name='가위바위보', help='가위바위보 게임을 합니다. 사용법: 가위바위보 <가위|바위|보>')
    async def rock_paper_scissors(self, ctx: commands.Context, user: str) -> None:
        if user not in RPS_CHOICES:
            await ctx.send(f'`{", ".join(RPS_CHOICES)}` 중 하나를 입력해주세요.')
            return

        bot_choice = random.choice(RPS_CHOICES)
        outcome = judge_rps(user, bot_choice)
        messages = {
            'draw': (f'{user} vs {bot_choice}  비겼습니다.', '비김'),
            'win': (f'{user} vs {bot_choice}  유저가 이겼습니다.', '승리!'),
            'lose': (f'{user} vs {bot_choice}  봇이 이겼습니다.', '패배...'),
        }
        reply, record = messages[outcome]

        await ctx.send(reply)
        await self.append_result(str(ctx.author), f'{user} vs {bot_choice} {record}\n')

    @game_group.command(name='전적', help='가위바위보 전적을 확인합니다.')
    async def game_board(self, ctx: commands.Context) -> None:
        result = await self.read_result(str(ctx.author))
        if not result:
            await ctx.send(f'{ctx.author}님의 가위바위보 전적이 존재하지 않습니다.')
            return

        if len(result) > MAX_RESULT_CHARS:
            result = f'...(이전 기록 생략)\n{result[-MAX_RESULT_CHARS:]}'
        await ctx.send(f'{ctx.author}님의 가위바위보 게임 전적입니다.\n{"=" * 30}\n{result}')


async def setup(bot: KSBot) -> None:
    await bot.add_cog(Game(bot))
