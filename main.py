from discord import Intents
from discord.message import Message
import os

from utils import CustomHelpCommand
from ksbot import KSBot


ks_bot = KSBot(command_prefix='!', intents=Intents.all())
ks_bot.help_command = CustomHelpCommand()


@ks_bot.command(description="Says hi")
async def hello(message: Message):
    await message.channel.send('Hi!')


@ks_bot.command(description="예의 주입할 것")
async def fuckyou(message: Message):
    await message.channel.send('응, 꺼져~')


DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN', '')
ks_bot.run(token=DISCORD_TOKEN)
