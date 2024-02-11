import os

from discord.ext import commands

from ks_bot.ks_bot import KSBot
from ks_bot.core.pubg_api import PUBG_Balancer
from ks_bot.common.error import *
from termcolor import cprint
import asyncio


class Balancer(commands.Cog):
    def __init__(self, bot: KSBot):
        self.bot = bot

        pubg_token = os.environ.get('PUBG_TOKEN')
        if not pubg_token:
            cprint("PUBG_TOKEN 환경 변수가 설정되지 않았습니다.", 'yellow')
            cprint("토큰을 설정하려면, 쉘의 설정 파일(.bashrc, .zshrc 등)에 다음을 추가하세요:", 'yellow')
            cprint('')
            cprint('    export PUBG_TOKEN="your_token_here"', 'yellow')
            cprint('')
            cprint("이후 새 쉘 세션을 시작하거나 설정 파일을 재로드하세요. (`source ~/.bashrc` or `source ~/.zshrc`)", 'yellow')
            raise ValueError("PUBG_TOKEN 환경 변수가 설정되지 않았습니다.")

        self.pubg_balancer = PUBG_Balancer(api_key=pubg_token, platform='steam')

    @commands.Cog.listener()
    async def on_ready(self):
        await self.pubg_balancer.connect_db()

    # @commands.command(
    #     name="스탯",
    #     help="유저의 스탯을 출력합니다.",
    #     description="유저의 스탯을 출력합니다.",
    #     aliases=['실력'],
    # )
    # async def player_stats(self, ctx: commands.Context, player_name: str):
    #     target_player = self.pubg_balancer.find_player(player_name)

    #     ctx.send(f"{player_name}의 스탯 정보")

    @commands.command(
        name="점수",
        help="유저의 스탯 점수를 출력합니다.",
        description="유저의 스탯 점수를 출력합니다.",
        aliases=['실력', '스탯점수', '실력점수'],
    )
    async def player_stats_score(self, ctx: commands.Context, player_name: str):
        try:
            stats = await self.pubg_balancer.get_stats(player_name)
            if isinstance(stats, Error_Balancer):
                await ctx.send(f"{player_name}의 스탯 점수를 가져오는데 실패했습니다. \nerror: {stats.message}")
            else:
                await ctx.send(f"{player_name}의 스탯 점수는 {stats.score:.04f} 입니다.")
        except Exception as e:
            # TODO: 에러 핸들링 추가
            pass


async def setup(bot: KSBot):
    await bot.add_cog(Balancer(bot))
