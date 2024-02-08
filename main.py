import asyncio
import os

from discord import Intents

from ks_bot.ks_bot import KSBot
from ks_bot.core.help import CustomHelpCommand
from termcolor import cprint


bot = KSBot(command_prefix='/', intents=Intents.all())
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


async def main():
    DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
    if not DISCORD_TOKEN:
        cprint("DISCORD_TOKEN 환경 변수가 설정되지 않았습니다.", 'yellow')
        cprint("토큰을 설정하려면, 쉘의 설정 파일(.bashrc, .zshrc 등)에 다음을 추가하세요:", 'yellow')
        cprint('    export DISCORD_TOKEN="your_token_here"', 'yellow')
        cprint("이후 새 쉘 세션을 시작하거나 설정 파일을 재로드하세요. (`source ~/.bashrc` or `source ~/.zshrc`)", 'yellow')
        return  # 토큰이 없으면 여기서 종료

    async with bot:
        await load_extensions()
        await bot.start(token=DISCORD_TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
