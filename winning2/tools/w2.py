"""Helpers for the winning2 verification scripts (used with the shared tools/replay.py and tools/printf_trace.py).

Button scripts (tools/drive.py syntax, counted from frame 10) for a new game, and Lua that collects what the game
prints. The game's printf is $C1:81A5 (format and arguments on the stack), which calls vsprintf $C1:7A7B(dst24, fmt24,
va24) and then puts $C1:5D35; printf_lua() traces vsprintf (tools/printf_trace.py) and returns the formatted text too.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
import printf_trace

A = " a:10 w200"                       # one press: 230 frames
# Title (~7000) -> 新しくゲームを始める -> introduction by 有馬 -> secretary list (井坂 is first) -> 井坂's card ->
# YES -> owner registration: surname / given name (あああ), age, birthday, sex, home (関東), crown name (アアアアア,
# before) -> how to be called -> 4-year-old horse for sale (cards 1/10 from press 71).
NEW_GAME = "w7000 start:10 w200"
# Program '96: the title takes START only after ~8000 frames and a longer press, then a menu (新しくゲームを始める
# first), and 有馬 has one more line (新しいレース日程に対応…); after these the A presses line up with the original's
# (the new-game copy runs at ~13555).
NEW_GAME_96 = "w8000 start:60 w200 start:60 w200" + A


def new_game(version: str) -> str:
    return NEW_GAME_96 if version == "program96" else NEW_GAME


def horse_card(version: str) -> str:
    """The next press shows the first 4-year-old's card (~23570 in the original, ~25165 in Program '96, where 井坂
    has one more line before the horses)."""
    return new_game(version) + A * (71 if version == "program96" else 70)


WRAM_PARAM = 0x1FF00                   # per-run values for the Lua hooks (WRAM $7F:FF00)

VSPRINTF = {"original": 0xC17A7B, "program96": 0xC13C4E}   # Program '96: printf $C1:4378


def printf_lua(version: str) -> str:
    return printf_trace.lua(VSPRINTF[version], fmt_at=8, va_at=12, va_size=3, dst_at=4)


COLLECT_LUA = """
function PARAM(i) return emu.read(0x1FF00 + i, emu.memType.snesWorkRam) end
function PARAM16(i) return PARAM(i) | PARAM(i + 1) << 8 end
local REC = {}
RESET_HOOKS = {}                                  -- functions run after every load (per-run state)
function REC_ADD(s) if #REC < 4000 then REC[#REC + 1] = s end end
function EXTRA_RESET()
  REC = {}
  if PF_RESET then PF_RESET() end
  for _, f in ipairs(RESET_HOOKS) do f() end
end
function EXTRA_SHOT()
  local s = "-\\n" .. table.concat(REC, "\\n")
  local h = (s:gsub(".", function(c) return string.format("%02x", c:byte()) end))
  return h .. " " .. (PF_SHOT and PF_SHOT() or "00")
end
"""


def records(raw: bytes) -> list[list[str]]:
    """Records added by REC_ADD (read [-2] of a run; read [-1] is the printf trace, printf_trace.parse)."""
    text = raw.decode("latin-1")
    return [line.split(" ") for line in text.split("\n") if line and line != "-"]
