from discord.ext import commands
from discord.member import Member


class KSBot(commands.Bot):
    async def on_ready(self) -> None:
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_member_join(self, member: Member) -> None:
        guild = member.guild
        if guild.system_channel is not None:
            to_send = f'Welcome {member.mention} to {guild.name}!'
            await guild.system_channel.send(to_send)
