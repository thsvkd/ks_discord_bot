from discord import Intents
from discord.message import Message
from discord.ext import commands
from ksbot import KSBot
import os

from utils import CustomHelpCommand


ks_bot = KSBot(command_prefix='!', intents=Intents.all())
ks_bot.help_command = CustomHelpCommand()


@ks_bot.command(description="Says hi")
async def hello(message: Message):
    await message.channel.send('Hi!')


@ks_bot.command(description="예의 주입할 것")
async def fuckyou(message: Message):
    await message.channel.send('응, 꺼져~')


# @ks_bot.command(name="help", description="Returns all commands available")
# async def help(message: Message):
#     helptext = "```"
#     for command in ks_bot.commands:
#         helptext += f"{command}\n"
#     helptext += "```"
#     await message.send(helptext)


DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN', '')
ks_bot.run(token=DISCORD_TOKEN)
