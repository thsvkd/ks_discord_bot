import json
from typing import Dict, List, Union


def print_dict_pretty(json_data: Union[Dict, List]) -> None:
    print(json.dumps(json_data, indent=4, ensure_ascii=False))
