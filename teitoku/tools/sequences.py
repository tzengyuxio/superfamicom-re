"""Button sequences of 提督の決断 for tools/replay.py and tools/drive.py, plus the "*n" repeat that drive.py has
and replay.py lacks. A press holds `hold` frames and is followed by 20 (replay.py / drive.py timing).
"""

# title -> 新しくゲームを始める -> scenario menu (cursor on 1), about frame 2460
TO_SCENARIOS = "w1800 start:10 w300 start:10 w300 a:10 w300"
# The 将校データ screen rolls each admiral's four abilities until a button stops it, then asks Y/N: two presses
# per admiral, at most 20 admirals per side
ROLL = " ".join(["a:10 w60"] * 40)
# 資料 menu of the main screen (b closes the 作戦 menu that the last press of new_game opens; 6th item)
DATA_MENU = "b:10 w60 " + "right:10 w60 " * 5 + "a:10 w100"
# 命令 menu (4th item)
ORDER_MENU = "b:10 w60 " + "right:10 w60 " * 3 + "a:10 w100"


def new_game(sc: int, side: int) -> str:
    """From the scenario menu: scenario sc (1-9), 1 player, side 0 = 日本軍 / 1 = 連合国軍, default difficulty,
    Y, map description, budget screen (b b b start a start), admiral roll -> main screen (fleet panel of the first
    fleet, about 7500 frames later). The last a opens the 作戦 menu."""
    return (f"{'down:10 w30 ' * (sc - 1)}a:10 w200 up:10 w100 a:10 w300 {'down:10 w60 ' if side else ''}"
            "a:10 w300 a:10 w300 a:10 w300 a:10 w300 b:10 w200 b:10 w200 b:10 w200 start:10 w200 a:10 w200 "
            f"start:10 w200 {ROLL} w200 a:10 w200")


def expand(steps: str) -> str:
    out = []
    for st in steps.split():
        s, _, n = st.partition("*")
        out += [s] * int(n or 1)
    return " ".join(out)


def end_frame(steps: str, start: int = 10) -> int:
    """Frame after the last step."""
    f = start
    for st in expand(steps).split():
        if st.startswith("w"):
            f += int(st[1:])
        elif not st.startswith("@"):
            f += int(st.partition(":")[2] or 4) + 20
    return f
