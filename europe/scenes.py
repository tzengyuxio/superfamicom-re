"""Button sequences (tools/drive.py syntax) and Lua capture helpers shared by the verify_*.py scripts.

Timings were measured with tools/drive.py; presses are held 10 frames (shorter presses are often missed).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import presses

# Power-on -> title (about frame 4200) -> start -> mode / scenario list, cursor on キャンペーンモード
TITLE = "w4600 start:10 w200 a:10 w300"


def scenario(k: int) -> str:
    """Scenario list -> scenario k (1-6) -> description -> これで良いですか: Y (the block is copied here)."""
    return " ".join(["down:10 w60"] * k) + " a:10 w300 a:10 w300"


# After scenario(): 何人で参戦 (0 / 1 / 2) -> 枢軸軍 / 連合軍 -> 戦闘を見るか -> Y
ZERO_PLAYERS = "a:10 w300 a:10 w300 a:10 w300 a:10 w600 a:10 w600"   # -> the battle map, computer vs computer
ONE_PLAYER_AXIS = "down:10 w60 a:10 w300 a:10 w300 a:10 w300 a:10 w300"   # -> 将軍の能力を検討せよ, first general
REVIEW_NEXT = "b:10 w300"                                             # next general of the review
# Scenario 1, one player, 枢軸軍: skip the review (b x 11), 貴官の分身を決定せよ (first general), then 作戦参謀,
# 情報参謀 and 第1-4師団長 (the next one down each time), 思い残すことはないか Y, 11 messages -> first command
# screen (戦術 移動 / 情報 編成 / 要請 空軍 / 特命 待機; move with down:4, down:10 skips two rows), about frame 17300
TO_COMMAND = (TITLE + " " + scenario(1) + " " + ONE_PLAYER_AXIS + " " + " ".join(["b:10 w100"] * 10)
              + " b:10 w600 a:10 w300 " + " ".join(["down:10 w60 a:10 w300"] * 6) + " a:10 w300 a:10 w600 "
              + " ".join(["a:10 w300"] * 11) + " w600")
# The same as 連合軍 (down before the side choice); scenario 1's Allies also have 10 generals
ONE_PLAYER_ALLIES = "down:10 w60 a:10 w300 down:10 w60 a:10 w300 a:10 w300 a:10 w300"
TO_COMMAND_ALLIES = TO_COMMAND.replace(ONE_PLAYER_AXIS, ONE_PLAYER_ALLIES)


def save_frame(steps: str) -> int:
    """First frame after the last press of steps and its wait, as tools/replay.py counts them."""
    last = presses(steps, 10)[-1]
    return last[0] + last[2] + 20 + int(steps.split()[-1][1:])


def length(steps: str) -> int:
    """Frames the steps take (a press is its hold + 20 frames)."""
    n = 0
    for st in steps.split():
        if st.startswith("w"):
            n += int(st[1:])
        else:
            n += int(st.partition(":")[2] or 4) + 20
    return n


# Lua: EVENTS collects strings without spaces; EXTRA_SHOT hands them to tools/replay.py, EXTRA_RESET clears them.
EVENTS_LUA = """
EVENTS = {}
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
local function hex(a, n)
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format("%02x", rd(a + i)) end
  return table.concat(t)
end
local function mem_hex(kind, a, n)
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format("%02x", emu.read(a + i, emu.memType[kind], false)) end
  return table.concat(t)
end
local function arg_ptr(off)
  local sp = emu.getState()["cpu.sp"]
  return rd(sp + off) + rd(sp + off + 1) * 256 + rd(sp + off + 2) * 65536
end
EXTRA_RESET = function() EVENTS = {} end
EXTRA_SHOT = function()  -- replay.py reads hex: the events joined by "," as hex of their characters
  local s = table.concat(EVENTS, ",")
  return (s:gsub(".", function(c) return string.format("%02x", string.byte(c)) end))
end
"""


def events(raw: bytes) -> list[str]:
    """The EVENTS of a run from the hex EXTRA_SHOT read (the last read of the run)."""
    s = raw.decode("ascii")
    return s.split(",") if s else []
