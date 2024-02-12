import json
import os
import traceback
from typing import Dict, List, Union
from datetime import datetime
from ks_bot.common.common import Timezone
from termcolor import cprint


def print_dict_pretty(json_data: Union[Dict, List]) -> None:
    print(json.dumps(json_data, indent=4, ensure_ascii=False))


def datetime_now(tz: Timezone = Timezone.KST) -> str:
    return datetime.now(tz=tz.to_pytz_timezone())


def get_discord_token() -> str:
    DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
    if not DISCORD_TOKEN:
        cprint("DISCORD_TOKEN 환경 변수가 설정되지 않았습니다.", 'yellow')
        cprint("토큰을 설정하려면, 쉘의 설정 파일(.bashrc, .zshrc 등)에 다음을 추가하세요:", 'yellow')
        cprint('')
        cprint('    export DISCORD_TOKEN="your_token_here"', 'yellow')
        cprint('')
        cprint("이후 새 쉘 세션을 시작하거나 설정 파일을 재로드하세요. (`source ~/.bashrc` or `source ~/.zshrc`)", 'yellow')
        return ''

    return DISCORD_TOKEN


def get_pubg_token() -> str:
    PUBG_TOKEN = os.environ.get('PUBG_TOKEN')
    if not PUBG_TOKEN:
        cprint("PUBG_TOKEN 환경 변수가 설정되지 않았습니다.", 'yellow')
        cprint("토큰을 설정하려면, 쉘의 설정 파일(.bashrc, .zshrc 등)에 다음을 추가하세요:", 'yellow')
        cprint('')
        cprint('    export PUBG_TOKEN="your_token_here"', 'yellow')
        cprint('')
        cprint("이후 새 쉘 세션을 시작하거나 설정 파일을 재로드하세요. (`source ~/.bashrc` or `source ~/.zshrc`)", 'yellow')
        return ''

    return PUBG_TOKEN


def print_error(e: Exception) -> None:
    traceback.print_exc()
    cprint(f'Exception type: {type(e).__name__}, Message: {e}', 'red')
