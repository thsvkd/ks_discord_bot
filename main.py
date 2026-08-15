"""하위 호환용 실행 스크립트. 실제 구현은 `ks_bot.__main__`에 있다.

권장 실행 방법: `python -m ks_bot`
"""

import sys

from ks_bot.__main__ import main

if __name__ == '__main__':
    sys.exit(main())
