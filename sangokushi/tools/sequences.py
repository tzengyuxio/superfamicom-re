"""Button sequences of スーパー三國志 for tools/drive.py and tools/replay.py (a press holds `hold` frames and is
followed by 20 more; "x*n" repeats a step; expand() and end_frame() come from tools/replay.py).

    TO_SCENARIOS   title -> 新しいゲーム -> the scenario list (frame ~1530)
    scenario(k)    -> scenario k (1-5), one player -> the ruler selection screen (8 rulers)
    TO_MAIN        scenario 1, 曹操, base stats, difficulty 1 ... -> 189-01 曹操's command screen at 7国 (~5880)
    INFO           main screen -> 情報 (6th item) -> its sub menu (他国 領地 武将 州別)
    MAP            main screen -> the whole map
    WAR_5 + WAR_START  main screen -> war on 5国 -> the battle field
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
from replay import end_frame, expand  # noqa: F401  (re-exported for the verify scripts)

TO_SCENARIOS = "w1040 start:10 w200 a:10 w200"


def scenario(k: int) -> str:
    return "down:10 w40 " * (k - 1) + "a:10 w200 up:10 w60 a:10 w300"


# the first ruler, B five times = the base stats (基本値), はい, difficulty, the next two questions, 他国戦闘 見ない
TO_MAIN = (TO_SCENARIOS + " " + scenario(1) + " a:10 w300 b:10 w100 b:10 w100 b:10 w100 b:10 w100 b:10 w200"
           " a:10 w300 a:10 w300 a:10 w300 right:10 w60 a:10 w300 a:10 w1200")
INFO = "down:10*5 w30 a:10 w100"
INFO_COUNTRY = INFO + " a:10 w150"                # 他国: "ﾄﾞﾉ国ｦ調ﾍﾞｻｾﾏｽｶ?" with the pointer on the map
INFO_TERRITORY = INFO + " down:10 w30 a:10 w200"  # 領地: own countries, 8 per page, two column sets (L / R)
INFO_PERSONS = INFO + " down:10*2 w30 a:10 w150"  # 武将: generals of the current country, two column sets
MAP = "b:10 w200"                                 # main screen -> the whole map (B)
# main screen -> 軍事 -> 戦争 -> pointer onto 5国 -> はい -> 曹操 and the next general, start -> 金 / 兵糧 / OK
# -> the battle field (the last press starts it: "曹操をどこに配置しますか", ~300 frames later)
WAR_5 = ("down:10 w40 a:10 w100 down:10 w40 down:10 w40 a:10 w100 down:4 w20 a:3 w100 a:10 w150 a:10 w60 down:10 w40"
         " a:10 w60 start:10 w150 a:10 w150 a:10 w150 a:10 w150 a:10 w150")
WAR_START = "a:10 w300"
