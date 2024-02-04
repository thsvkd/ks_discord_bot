import discord
import os

from discord.ext import commands

from module.ksbot import KSBot
from utils.pubg_api import PUBG_Balancer


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
    #     if not self.pubg_balancer.is_player_exist(player_name):
    #         self.pubg_balancer.add_player(player_name)
    #         self.pubg_balancer.update_player_data(player_name)

    #     target_player = self.pubg_balancer.find_player(player_name)

    #     ctx.send(f"{player_name}의 스탯 정보")

    @commands.command(
        name="점수",
        help="유저의 스탯 점수를 출력합니다.",
        description="유저의 스탯 점수를 출력합니다.",
        aliases=['실력', '스탯점수', '실력점수'],
    )
    async def player_stats_score(self, ctx, player_name: str):
        if not self.pubg_balancer.is_player_exist(player_name):
            self.pubg_balancer.add_player(player_name)

        stats_score = self.pubg_balancer.get_stats_score(player_name)
        await ctx.send(f"{player_name}의 스탯 점수는 {stats_score}입니다.")


async def setup(bot: KSBot):
    await bot.add_cog(Balancer(bot))
