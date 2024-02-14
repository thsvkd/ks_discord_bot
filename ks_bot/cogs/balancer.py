import os

import discord
from discord.ext import commands, tasks
from discord import Member, Status

from ks_bot.ks_bot import KSBot
from ks_bot.core.pubg_balancer import PUBG_Balancer
from ks_bot.common.error import *
from ks_bot.utils import *
from typing import Union, Tuple
import asyncio


class Balancer(commands.Cog):
    PUBG_APP_NAME = 'PUBG: BATTLEGROUNDS'

    def __init__(self, bot: KSBot):
        self.bot = bot
        self.pubg_balancer = PUBG_Balancer(api_key=get_pubg_token(), platform='steam')

    @commands.Cog.listener()
    async def on_ready(self):
        await self.pubg_balancer.connect_db()
        self.check_member_status.start()

    async def cog_unload(self):
        await self.pubg_balancer.close_db()

    @tasks.loop(minutes=30)
    async def check_member_status(self):
        '''
        주기적으로 멤버가 게임을 플레이 중인지 확인하여 플레이어 정보를 업데이트합니다.
        '''
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.activity and member.activity.name == Balancer.PUBG_APP_NAME:
                    player_id = self.parse_player_id(discord_member=member)
                    player = await self.pubg_balancer._request_single_player(player_id)
                    if not await self.pubg_balancer.is_player_exist(player.name):
                        await self.pubg_balancer.insert_player(player)
                    else:
                        await self.pubg_balancer.update_player(player)

                    await self.pubg_balancer.update_discord_id(player.name, member.id)

    def parse_discord_display_name(self, display_name: str) -> str:
        return display_name.split('|')[1].strip()

    def parse_discord_id(self, input: str) -> str | None:
        if input.startswith("<@") and input.endswith(">"):
            return input.strip("<@!>")

    def parse_player_id(self, discord_member: Member) -> str | None:
        return discord_member.activity.party['id'].split('-')[0]

    async def parse_command_input(self, ctx: commands.Context, input: Union[Member, str]) -> Tuple[str, str | None]:
        if input:
            discord_id = self.parse_discord_id(input)
            if not discord_id:
                # if input is not `@mention`, input is raw player name
                player_name = input
                return player_name, discord_id

            discord_member = ctx.guild.get_member(int(discord_id))
            if not discord_member:
                # discord_member is not exist in the server
                raise PlayerNotFoundError_Balancer(player_name=input)

            try:
                player_name = await self.pubg_balancer.get_player_name_by_discord_id(discord_id=discord_id)
                return player_name, discord_id
            except PlayerNotFoundError_Balancer:
                if discord_member.activity == None or not Balancer.PUBG_APP_NAME == discord_member.activity.name:
                    player_name = self.parse_discord_display_name(discord_member.display_name)
                    return player_name, discord_id

            try:
                player_id = self.parse_player_id(discord_member=discord_member)
                player = await self.pubg_balancer._request_single_player(player_id)
                player_name = player.name
                return player_name, discord_id
            except PlayerNotFoundError_Balancer:
                player_name = self.parse_discord_display_name(discord_member.display_name)
                return player_name, discord_id
        else:
            discord_id = None
            player_name = ctx.author.display_name
            return player_name, discord_id

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
            player_name, discord_id = await self.parse_command_input(ctx, input)
            await self.pubg_balancer.update_discord_id(player_name, discord_id)
            stats_future = self.pubg_balancer.get_stats(player_name)

            embed = discord.Embed(
                title="삐삑! 전투력 측정 중...", description="매치정보를 받아오는 중입니다, 잠시만 기다려주세요...", color=embed_color
            )
            embed.set_image(
                url='https://lh3.googleusercontent.com/u/0/drive-viewer/AEYmBYRiFGFgeh92WnsjsTBvEi1rxCKjEpbAYq3pi5FBM_asqA6nKFIOl885D9WzQJ6dC0Fj43nAGt0KQhOvtvlr1desweLuHQ=w2560-h1271'
            )
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
                new_embed.set_image(
                    url='https://lh3.googleusercontent.com/u/0/drive-viewer/AEYmBYT7wt9V9d2PPR9BtqUb8beBULaeOCLojdCNPMdy5SZ0fOEzCuIS_v0f09CwtrnS8cDXeKGl7_m7EyGij9Fh1_i_VPOZRw=w2560-h1271'
                )
            elif 5 <= stats.score < 10:
                new_embed = discord.Embed(
                    title="전투력 측정 완료! 좀 치는 녀석이군...",
                    description=stats_description,
                    color=embed_color,
                )
                new_embed.set_image(
                    url='https://lh3.googleusercontent.com/u/0/drive-viewer/AEYmBYR1jHdQyQMvviH3lMQbCO8Q3qgOaFYBFGZ9qlOEOy7ikThM56R2L_PIyT2jkEpzYac0TZOPT9L09Fijb9VqIUOiYd0syw=w2560-h1271'
                )
            elif 10 <= stats.score < 15:
                new_embed = discord.Embed(
                    title="전투력 측정 완료! 이, 이녀석 조심해야겠어...!",
                    description=stats_description,
                    color=embed_color,
                )
                new_embed.set_image(
                    url='https://lh3.googleusercontent.com/u/0/drive-viewer/AEYmBYRkUJv1XYMkyn4a-NPazFnnNQ09O7jTLBppgpjTxlpkJ1smPqIa2sJlBgurJP042ax5HfwTMnziXCdnHRbEt74WZS8low=w2560-h1271'
                )
            elif 15 <= stats.score:
                new_embed = discord.Embed(
                    title="전투력 측정 완료! 스카우터가... 터져버렸어?!?",
                    description=stats_description,
                    color=embed_color,
                )
                new_embed.set_image(
                    url='https://lh3.googleusercontent.com/u/0/drive-viewer/AEYmBYQ3qw-Prf9G2V758nIn1Xzx3YLe5RTCI-ibi4Q7rtYHqC8283wYpqV0oS8PkNsyjwJGJWUOjOcf_ou1T9YnQ2PMyroC_w=w2560-h1271'
                )
            await message.edit(embed=new_embed)
        except PlayerNotFoundError_Balancer as e:
            print_error(e)
            await message.edit(content=f"플레이어 `{player_name}`을 찾을 수 없습니다.", embed=None)
        except Exception as e:
            print_error(e)


async def setup(bot: KSBot):
    await bot.add_cog(Balancer(bot))
