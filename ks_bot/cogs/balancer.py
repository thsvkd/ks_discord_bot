import os

from discord.ext import commands

from ks_bot.ks_bot import KSBot
from ks_bot.core.pubg_api import PUBG_Balancer
from ks_bot.common.error import *


class Balancer(commands.Cog):
    def __init__(self, bot: KSBot):
        self.bot = bot
        self.pubg_balancer = PUBG_Balancer(api_key=os.environ['PUBG_TOKEN'], platform='steam')

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
        stats_score = self.pubg_balancer.get_stats_score(player_name)
        if isinstance(stats_score, Error_Balancer):
            await ctx.send(f"{player_name}의 스탯 점수를 가져오는데 실패했습니다. \nerror: {stats_score.message}")
        else:
            await ctx.send(f"{player_name}의 스탯 점수는 {stats_score:.04f} 입니다.")


async def setup(bot: KSBot):
    await bot.add_cog(Balancer(bot))
