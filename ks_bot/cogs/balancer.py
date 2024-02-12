import os

import discord
from discord.ext import commands

from ks_bot.ks_bot import KSBot
from ks_bot.core.pubg_balancer import PUBG_Balancer
from ks_bot.common.error import *
from ks_bot.utils import *
from termcolor import cprint
import asyncio


class Balancer(commands.Cog):
    PUBG_APP_NAME = 'PUBG: BATTLEGROUNDS'

    def __init__(self, bot: KSBot):
        self.bot = bot
        self.pubg_balancer = PUBG_Balancer(api_key=get_pubg_token(), platform='steam')

    @commands.Cog.listener()
    async def on_ready(self):
        await self.pubg_balancer.connect_db()

    async def cog_unload(self):
        await self.pubg_balancer.close_db()

    def parse_display_name(self, display_name: str) -> str:
        return display_name.split('|')[1].strip()

    async def input_to_player_name(self, ctx: commands.Context, input: Union[discord.Member, str]) -> str:
        if input:
            if not (input.startswith("<@") and input.endswith(">")):
                player_name = input
                return player_name

            member_id = input.strip("<@!>")
            member = ctx.guild.get_member(int(member_id))

            if not member:
                raise PlayerNotFoundError_Balancer(player_name=input)

            if member.activity == None or not Balancer.PUBG_APP_NAME == member.activity.name:
                player_name = self.parse_display_name(member.display_name)
                return player_name

            try:
                player_id = member.activity.party['id'].split('-')[0]
                player = await self.pubg_balancer._request_single_player(player_id)
                player_name = player.name
                return player_name
            except PlayerNotFoundError_Balancer:
                player_name = self.parse_display_name(member.display_name)
                return player_name
        else:
            player_name = ctx.author.display_name
            return player_name

    # @commands.command(
    #     name="스탯",
    #     help="유저의 스탯을 출력합async니다.",
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
        aliases=['실력', '스탯점수', '실력점수', 'score'],
    )
    async def player_stats_score(self, ctx: commands.Context, *, input: str = None):
        # async def player_stats_score(self, ctx: commands.Context, player_name: str):
        embed_color = 0xD04848

        try:
            player_name = await self.input_to_player_name(ctx, input)
            stats_future = self.pubg_balancer.get_stats(player_name)
            embed = discord.Embed(
                title="삐삑! 전투력 측정 중...", description="매치정보를 받아오는 중입니다, 잠시만 기다려주세요...", color=embed_color
            )
            embed.set_image(url='https://drive.google.com/file/d/1limriS7qLdNKEwd6MdfFKODoySDfgEhc/view?usp=sharing')
            message = await ctx.send(embed=embed)
            await asyncio.sleep(1)

            # await ctx.send(f"{player_name}의 스탯 점수는 {stats.sco re:.04f} 입니다.")
            stats = await stats_future
            stats_description = f"**`{player_name}`**의 스탯 점수는 **`{stats.score:.04f}`** 입니다."
            if 0 < stats.score < 5:
                new_embed = discord.Embed(
                    title="전투력 측정 완료! 애송이로군요!",
                    description=stats_description,
                    color=embed_color,
                )
                new_embed.set_image(url='https://drive.google.com/file/d/18w2ct3QKB9uBzMOG4n-dG0rdviBAc0WR/view?usp=sharing')
            elif 5 <= stats.score < 10:
                new_embed = discord.Embed(
                    title="전투력 측정 완료! 좀 치는 녀석이군...",
                    description=stats_description,
                    color=embed_color,
                )
                new_embed.set_image(url='https://drive.google.com/file/d/10xlxf4frQuA393OKBZ8mdUloIduYEK_6/view?usp=sharing')
            elif 10 <= stats.score < 15:
                new_embed = discord.Embed(
                    title="전투력 측정 완료! 이, 이녀석 조심해야겠어...!",
                    description=stats_description,
                    color=embed_color,
                )
                new_embed.set_image(url='https://drive.google.com/file/d/1LEIsR0ZbxWqE2oC98bUFJR2nlB7b0adx/view?usp=sharing')
            elif 15 <= stats.score:
                new_embed = discord.Embed(
                    title="전투력 측정 완료! 스카우터가... 터져버렸어?!?",
                    description=stats_description,
                    color=embed_color,
                )
                new_embed.set_image(url='https://drive.google.com/file/d/1HpEUmh9zy0H4KXHjtOY8PJhomhIzt-U2/view?usp=sharing')
            await message.edit(embed=new_embed)
        except PlayerNotFoundError_Balancer as e:
            print_error(e)
            await message.edit(content=f"플레이어 `{player_name}`을 찾을 수 없습니다.", embed=None)
        except Exception as e:
            print_error(e)


async def setup(bot: KSBot):
    await bot.add_cog(Balancer(bot))
