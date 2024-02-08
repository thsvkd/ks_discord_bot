import random
import os

from discord.ext import commands

from ks_bot.ks_bot import KSBot


async def make_dir(directory_name: str):
    try:
        if not os.path.exists(directory_name):
            os.makedirs(directory_name)
    except OSError:
        print('Error: makedirs()')


async def add_result(directory_name: str, user_name: str, result: str):
    file_path = directory_name + '/' + user_name + '.txt'
    if os.path.exists(file_path):
        with open(file_path, 'a', encoding='UTF-8') as f:
            f.write(result)
    else:
        with open(file_path, 'w', encoding='UTF-8') as f:
            f.write(result)


class Game(commands.Cog):
    def __init__(self, bot: KSBot):
        self.bot = bot

    @commands.command(name="주사위", help='주사위를 굴립니다.')
    async def dice(self, ctx: commands.Context):
        randnum = random.randint(1, 6)
        await ctx.send(f'주사위 결과는 {randnum} 입니다.')

    @commands.command(name="뽑기", help='뽑기를 합니다.')
    async def mining(self, ctx: commands.Context):
        minerals = ['다이아몬드', '루비', '에메랄드', '자수정', '철', '석탄']
        weights = [1, 3, 6, 15, 25, 50]
        results = random.choices(minerals, weights=weights, k=5)
        await ctx.send(', '.join(results) + ' 광물들을 획득하였습니다.')

    @commands.command(name="가위바위보", help='가위바위보 게임을 합니다.')
    async def game(self, ctx: commands.Context, user: str):
        rps_table = ['가위', '바위', '보']
        bot = random.choice(rps_table)
        result = rps_table.index(user) - rps_table.index(bot)
        if result == 0:
            result_text = f'{user} vs {bot} 비김'
            await ctx.send(f'{user} vs {bot}  비겼습니다.')
        elif result == 1 or result == -2:
            result_text = f'{user} vs {bot} 승리!'
            await ctx.send(f'{user} vs {bot}  유저가 이겼습니다.')
        else:
            result_text = f'{user} vs {bot} 패배...'
            await ctx.send(f'{user} vs {bot}  봇이 이겼습니다.')

        directory_name = "game_result"
        await make_dir(directory_name)
        await add_result(directory_name, str(ctx.author), result_text + '\n')

    @commands.command(name="전적", help='가위바위보 전적을 확인합니다.')
    async def game_board(self, ctx: commands.Context):
        user_name = str(ctx.author)
        file_path = "game_result/" + user_name + ".txt"
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="UTF-8") as f:
                result = f.read()
            await ctx.send(f'{ctx.author}님의 가위바위보 게임 전적입니다.\n==============================\n' + result)
        else:
            await ctx.send(f'{ctx.author}님의 가위바위보 전적이 존재하지 않습니다.')


async def setup(bot: KSBot):
    await bot.add_cog(Game(bot))
