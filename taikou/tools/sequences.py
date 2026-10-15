"""Button sequences of 太閤立志伝 for tools/replay.py (a press holds `hold` frames and is followed by 20; expand()
and end_frame() come from tools/replay.py), plus split_at() to cut a sequence at a savestate frame.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
from replay import end_frame, expand  # noqa: F401  (re-exported for the verify scripts)

# title -> 新たな物語を始める -> ... -> type selection (猛将型 能吏型 知将型 武芸者), about frame 3200
TO_TYPES = "w700 start:10 w800 start:4*12 w100 a:10 w300 a:10 w300 a:10 w300 a:10 w300 a:10 w300"
# -> pick the type, roll the stats, hold a to spend the 50 bonus points on 外交, confirm, opening events ->
# the Japan map in 尾張 (1560-05-18, about frame 12700)
TO_MAP = TO_TYPES + " a:900 w100 w300 a:10*170 a:10*30 a:10*30 a:10*30"
# -> more events -> the battle of 桶狭間 (about frame 15400); a opens the command menu, right = 情報,
# a = "どの部隊を調べようか" with the cursor on 木下藤吉郎's unit; the next a opens his info screen
TO_INFO = TO_MAP + " a:10*80 w300 w300 a:10 w60 right:10 w30 a:10 w60 w100 a:10 w100 w200"


def split_at(steps: str, frame: int, start: int = 10) -> tuple[str, int, str]:
    """(steps before, savestate frame, steps after): the cut is at the last step boundary at or before frame, so
    the steps after can be replayed from a savestate taken there."""
    f, cut, words = start, start, expand(steps).split()
    k = 0
    for i, st in enumerate(words):
        if f > frame:
            break
        cut, k = f, i
        f += int(st[1:]) if st.startswith("w") else int(st.partition(":")[2] or 4) + 20
    else:
        cut, k = f, len(words)
    return " ".join(words[:k]), cut, " ".join(words[k:])
