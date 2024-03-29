import asyncio
import os

from discord import Intents

from ks_bot.ks_bot import KSBot
from ks_bot.core.help import CustomHelpCommand
from ks_bot.utils import *

intents = Intents.all()
intents.members = True
bot = KSBot(command_prefix='/', intents=intents)

bot.help_command = CustomHelpCommand()


async def load_extensions():
    cogs_folder = 'ks_bot/cogs'
    abs_cogs_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), cogs_folder)
    for ext in os.listdir(abs_cogs_path):
        if ext.endswith(".py"):
            module_name = ext.split('.')[0]
            module_import_path = f'{cogs_folder.replace("/", ".")}.{module_name}'
            print(f'Load {module_import_path}')
            await bot.load_extension(module_import_path)


async def main() -> None:
    DISCORD_TOKEN = get_discord_token()

    async with bot:
        await load_extensions()
        await bot.start(token=DISCORD_TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
