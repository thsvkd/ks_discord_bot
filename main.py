import asyncio
import os

from discord import Intents

from module.ksbot import KSBot
from utils.help import CustomHelpCommand


bot = KSBot(command_prefix='!', intents=Intents.all())
bot.help_command = CustomHelpCommand()


async def load_extensions():
    cogs_folder = 'cogs'
    abs_cogs_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), cogs_folder)
    for ext in os.listdir(abs_cogs_path):
        if ext.endswith(".py"):
            cog_module_name = f"{cogs_folder}.{ext.split('.')[0]}"
            print(f'Load {cog_module_name}')
            await bot.load_extension(cog_module_name)


async def main():
    async with bot:
        DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN', '')
        await load_extensions()
        await bot.start(token=DISCORD_TOKEN)


asyncio.run(main())
