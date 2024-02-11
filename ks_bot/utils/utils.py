import json
from typing import Dict, List, Union
from datetime import datetime
from ks_bot.common.common import Timezone


def print_dict_pretty(json_data: Union[Dict, List]) -> None:
    print(json.dumps(json_data, indent=4, ensure_ascii=False))


def datetime_now(tz: Timezone = Timezone.KST) -> str:
    return datetime.now(tz=tz.to_pytz_timezone())
