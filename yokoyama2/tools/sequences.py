"""Button scripts (tools/drive.py syntax, counted from frame 10), WRAM addresses and Lua hooks of the yokoyama2
verifications.

Boot: title (START is taken only after about frame 1800: the first START at 1510 is ignored) -> START ->
最初から始める (a) -> シナリオ選択 (189 / 200 / 215, down to move) -> 君主選択 (a list, down to move) -> 難易度選択
(上級 中級 初級 エディット) -> opening text (3 presses) -> the scenario loader $99:E436 -> the map of the first
month: events (each needs a press) and the computer factions' turns (each "○○軍戦略中" waits for a press), then
the player's turn (the cursor appears on the map).

On the map: a = the player's country panel and the command menu (政略 軍略 政業); X = the information screen of
the country under the cursor. 政略 -> 人事 (down, a) -> 人材 (a) -> 選択 (a) -> officer list; X there = the
officer's detail screen (name, reading, faction, 官位, all fields, face).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
from replay import end_frame, expand  # noqa: F401  (re-exported)

TO_SCENARIOS = "w1500 start:20 w300 start:20 w200 a:10 w200"     # scenario list
OPENING = "a:10 w300 w300 a:10 w300 a:10 w300 a:10 w300"           # difficulty -> opening text -> loader


def moves(button: str, n: int) -> str:
    return "".join(f" {button}:6 w60" for _ in range(n))


def scenario(k: int, ruler: int = 0, difficulty: int = 1) -> str:
    """From the scenario list: scenario k (0 189, 1 200, 2 215), ruler list item, difficulty (0 上級 1 中級 2 初級),
    through the opening text (the loader runs at its end)."""
    return ("w30" + moves("down", k) + " a:10 w200" + moves("down", ruler) + " a:10 w300" + moves("down", difficulty)
            + " " + OPENING).strip()


PLAYER = 0x0184               # player's faction
SCENARIO = 0x017A
DIFFICULTY_FLAGS = 0x0178     # 0x88 上級, 0x155 中級, 0x222 初級


def loader_lua(addr: int, lo: int, hi: int) -> str:
    """Lua: dump WRAM lo..hi-1 when the program reaches addr (rom.LOADER_DONE: right after the loader)."""
    return f"""
local dump="00"
for _,a in ipairs({{{addr & 0x7FFFFF}, {addr | 0x800000}}}) do
  emu.addMemoryCallback(function()
    local s={{}}
    for i={lo},{hi - 1} do s[#s+1]=string.format("%02x", emu.read(i, emu.memType.snesWorkRam, false)) end
    dump=table.concat(s)
  end, emu.callbackType.exec, a)
end
function EXTRA_RESET() dump="00" end
function EXTRA_SHOT() local s=dump; dump="00"; return s end
"""

# Presses after the opening text until the player's turn (events and the "○○軍戦略中" of the computer factions
# before the player, each waiting for a press), playing 劉備 at 中級
TURN_PRESSES = [3, 2, 0]
TO_MAP = [TO_SCENARIOS + " " + scenario(k) + " a:10 w300" * n + " w400" for k, n in enumerate(TURN_PRESSES)]
HOME = [10, 4, 28]            # the player's (劉備) country at the start: 并州 (189), 下邳 (200), 成都 (215)
# From the player's turn (save here; the officer lists of the country are built when its panel opens): panel ->
# 政略 -> 人事 -> 人材 -> 選択 (the officer list, sorted by 政治力) -> X (detail screen of the first officer)
DETAIL_PRE = "w30 a:10 w200 a:10 w200 down:6 w60 a:10 w200 a:10 w200 a:10 w200"
DETAIL_STEPS = DETAIL_PRE + " x:10 w300"
DETAIL_FROM = end_frame(DETAIL_PRE, 0)    # frame (after the savestate) of the X press
DETAIL_SHOT = end_frame(DETAIL_STEPS, 0)
FACE_OBJ_VRAM = 0xC000        # byte address of the OBJ tiles on the detail screen
FACE_X, FACE_Y = 104, 22      # top-left of the face box on the detail screen

# Lua: log every code $80:8C2E prints from frame CODES_FROM on; EXTRA_SHOT hands them over (4 hex digits each)
CODES_LUA = """
local codes={}
local cf=0
CODES_FROM=CODES_FROM or 0
emu.addEventCallback(function() cf=cf+1 end, emu.eventType.endFrame)
for _,a in ipairs({0x008C2E, 0x808C2E}) do
  emu.addMemoryCallback(function()
    if cf>=CODES_FROM then codes[#codes+1]=string.format("%04x", emu.getState()["cpu.a"] & 0xFFFF) end
  end, emu.callbackType.exec, a)
end
function EXTRA_RESET() codes={}; cf=0 end
function EXTRA_SHOT() local s=table.concat(codes); codes={}; if s=="" then s="00" end; return s end
"""


def codes(hexstr: bytes) -> list[int]:
    """EXTRA_SHOT bytes of CODES_LUA -> list of codes."""
    return [hexstr[i] << 8 | hexstr[i + 1] for i in range(0, len(hexstr) - 1, 2)]
