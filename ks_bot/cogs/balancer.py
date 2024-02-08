import os

from discord.ext import commands

from ks_bot.ks_bot import KSBot
from ks_bot.core.pubg_api import PUBG_Balancer, ErrorCode_Balancer


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
        if not self.pubg_balancer.is_player_exist(player_name):
            self.pubg_balancer.add_player(player_name)

        stats_score = self.pubg_balancer.get_stats_score(player_name)
        if stats_score == ErrorCode_Balancer.PLAYER_NOT_FOUND:
            await ctx.send(f"{player_name}의 스탯 점수를 가져오는데 실패했습니다. 플레이어 이름을 정확히 입력해주세요.")
            return

        await ctx.send(f"{player_name}의 스탯 점수는 {stats_score:.04f} 입니다.")


async def setup(bot: KSBot):
    await bot.add_cog(Balancer(bot))
