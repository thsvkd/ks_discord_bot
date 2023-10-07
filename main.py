import asyncio
import os

from discord import Intents

from module.ksbot import KSBot
from utils.help import CustomHelpCommand


bot = KSBot(command_prefix='!', intents=Intents.all())
bot.help_command = CustomHelpCommand()


# cogs 폴더에 존재하는 cogs(.py파일) 로드
async def load_extensions():
    cogs_folder = 'cogs'
    abs_cogs_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), cogs_folder)
    for ext in os.listdir(abs_cogs_path):
        if ext.endswith(".py"):
            cog_module_name = f"{cogs_folder}.{ext.split('.')[0]}"
            print(f'Load {cog_module_name}')
            await bot.load_extension(cog_module_name)  # .py 부분을 떼고 cog의 이름만 추출


# @bot.command(description="Says hi")
# async def hello(message: Message):
#     await message.channel.send('Hi!')


# @bot.command(description="예의 주입할 것")
# async def fuckyou(message: Message):
#     await message.channel.send('응, 꺼져~')


async def main():
    async with bot:
        await load_extensions()
        # await bot.load_extension(f"Cogs.ping")
        DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN', '')
        await bot.start(token=DISCORD_TOKEN)


asyncio.run(main())
