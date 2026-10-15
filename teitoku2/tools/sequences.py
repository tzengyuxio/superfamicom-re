"""Button sequences of 提督の決断II for tools/replay.py, plus the "*n" repeat that replay.py lacks.
A press holds `hold` frames and is followed by 20 (replay.py timing).
"""

# title -> NEW GAME -> scenario menu (cursor on scenario 0)
TO_SCENARIOS = "w1800 start:10 w200 start:10 w800 a:10 w500"
# 設定 screen: down to 助言表示, right, down to 決定 (whether 助言 is switched off is not checked; the advice
# that still shows on the main screen is closed by the last press of new_game)
SETTINGS = "down:10*6 w60 right:10 w60 down:10 w60 a:10 w500"
# top menu of the main screen (委任 配備 一覧 作戦 情報 公布 機能)
TOP = "x:10 w100 x:10 w100"
# 情報 menu (5th item); the cursor starts on 艦船情報 / 就航艦船
INFO = TOP + " right:10 w60*4 a:10 w300"
# 一覧 menu (3rd item): 艦隊 海航空隊 陸戦隊 潜水艦 基地 拠点 陸軍部隊
LIST = TOP + " right:10 w60*2 a:10 w200"
# 作戦 -> 人事 (海軍提督 / 陸軍将軍)
PERSONNEL = TOP + " right:10 w60*3 a:10 w100 down:10 w60 down:10 w60 a:10 w300"


def new_game(sc: int) -> str:
    """From the scenario menu: scenario sc (0-9), its description, 大日本帝国 (1 player), 初級, the 設定 screen
    (SETTINGS), then the opening messages and the first advice up to the main screen (日本軍移動命令)."""
    return f"{'down:10 w100 ' * sc}a:10 w500 a:10 w500 a:10 w500 a:10 w500 {SETTINGS} {'a:10 w500 ' * 9}w500"


def expand(steps: str) -> str:
    """'x:10*3' -> 'x:10 x:10 x:10', 'w60*4' -> 'w60 w60 w60 w60'; a step 'right:10 w60*4' repeats the pair."""
    out = []
    toks = steps.split()
    i = 0
    while i < len(toks):
        s, _, n = toks[i].partition("*")
        if n and s.startswith("w") and out and not out[-1].startswith("w"):  # "press wN*k": repeat the pair
            press = out.pop()
            out += [press, s] * int(n)
        else:
            out += [s] * int(n or 1)
        i += 1
    return " ".join(out)


def end_frame(steps: str, start: int = 10) -> int:
    """Frame after the last step."""
    f = start
    for st in expand(steps).split():
        if st.startswith("w"):
            f += int(st[1:])
        else:
            f += int(st.partition(":")[2] or 4) + 20
    return f
