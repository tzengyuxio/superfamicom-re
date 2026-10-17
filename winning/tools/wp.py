"""Helpers for the winning verification scripts (used with the shared tools/replay.py).

Button scripts (tools/drive.py syntax, counted from frame 10) for a new game, and Lua snippets that collect what
the game does and hand it back through replay's EXTRA_SHOT as one hex string (records separated by \\n):

  PRINT_LUA  every vprintf ($C2:1E9A; format pointer at S+4, va list in bank 0 at S+8)
             -> "P fmt args(6 words) str(va+0) str(va+2) str(va+6)" (strings as hex; a %s argument is a 4-byte
             pointer whose top byte is ignored) and every puts ($C2:06E9, string pointer at S+4) -> "S str"
  FACE_LUA   every face draw ($CA:2DA7, code at S+$44) -> "F code"

parse() turns the hex string back into records. EXTRA_RESET clears the collected records after each load.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))

A200 = " a:10 w200"
# Title (PUSH START at ~6300) -> "ゲームを最初からやりなおす" -> the secretary's introduction -> home (関東) ->
# name (A x 3 = あああ) -> sex / age / blood type / how to be called -> pick a 4-year-old (5 shown) and name it
# (A x 9 = アアアアアアアアア) -> pick a 3-year-old; the right press moves the cursor so it is named イイイイイイイイイ
# (otherwise "その馬名はすでに使用") -> trainer list (from ~20900).
NEW_GAME = "w6300 start:10 w300 down:10 w60" + " a:10 w300" * 5
TRAINER_LIST = NEW_GAME + A200 * 44 + " right:10 w60" + A200 * 9          # ends at 20660
# From TRAINER_LIST: the 1st press shows the secretary's question (~20740), the 2nd the trainer list (~20940), the
# 3rd trainer 0's info window (~21240). The first trainer (奥山) refuses an unknown owner; the second one (松岡) is picked. The first right press in
# the list does nothing until an info window has been shown.
TRAINER_CHOSEN = TRAINER_LIST + A200 * 2 + " right:10 w60" + A200 * 2 + " right:10 w60" + A200 * 3
# + 27 presses: January 1997, 松岡 visits, 月刊競馬ニュース (leaders, then the graded races of the month)
MAGAZINE = TRAINER_CHOSEN + A200 * 27                                       # ends at 28660
RACE_PAGE = MAGAZINE + A200                                                 # 1月の重賞 page 1 is drawn ~300 later

INIT_DONE_FRAME = 6600          # the new-game tables are copied at ~6505 (title screen, before any choice)
NAME_SCAN_FRAME = 16700         # the name entry checks the typed name against every horse at ~16800-16900

WRAM_PARAM = 0xFF00             # per-run values for the Lua hooks (zero in every dump of the game)

COLLECT_LUA = """
local REC = {}
function REC_ADD(s) if #REC < 6000 then REC[#REC + 1] = s end end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
function MEMSTR(a, n)
  local t = {}
  for i = 0, (n or 48) - 1 do
    local c = rd(a + i)
    if c == 0 then break end
    t[#t + 1] = string.format("%02x", c)
  end
  return #t > 0 and table.concat(t) or "-"
end
function PARAM(i) return emu.read(0xFF00 + i, emu.memType.snesWorkRam) end
function EXTRA_RESET() REC = {} end
function EXTRA_SHOT()
  local s = "-\\n" .. table.concat(REC, "\\n")    -- never empty: replay drops an empty last field
  return (s:gsub(".", function(c) return string.format("%02x", c:byte()) end))
end
"""

PRINT_LUA = """
emu.addMemoryCallback(function()
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local function p24(a) return rd(a) | rd(a + 1) << 8 | rd(a + 2) << 16 end
  local sp = emu.getState()["cpu.sp"]
  local va = rd(sp + 8) | rd(sp + 9) << 8
  local a = {}
  for i = 0, 5 do a[#a + 1] = string.format("%04x", rd(va + 2 * i) | rd(va + 2 * i + 1) << 8) end
  REC_ADD(string.format("P %s %s %s %s %s", MEMSTR(p24(sp + 4), 80), table.concat(a, ","), MEMSTR(p24(va)),
    MEMSTR(p24(va + 2)), MEMSTR(p24(va + 6))))
end, emu.callbackType.exec, 0xC21E9A)
emu.addMemoryCallback(function()
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local sp = emu.getState()["cpu.sp"]
  REC_ADD("S " .. MEMSTR(rd(sp + 4) | rd(sp + 5) << 8 | rd(sp + 6) << 16))
end, emu.callbackType.exec, 0xC206E9)
"""

FACE_LUA = """
emu.addMemoryCallback(function()
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local sp = emu.getState()["cpu.sp"]
  REC_ADD(string.format("F %04x", rd(sp + 0x44) | rd(sp + 0x45) << 8))
end, emu.callbackType.exec, 0xCA2DAD)
"""


def parse(raw: bytes) -> list[list[str]]:
    """Records of one run's EXTRA_SHOT (the last read of replay's result)."""
    text = raw.decode("latin-1")
    return [line.split(" ") for line in text.split("\n") if line and line != "-"]


def prints(records: list[list[str]]) -> list[dict]:
    out = []
    for r in records:
        if r[0] == "P":
            out.append({"fmt": unhex(r[1]), "args": [int(x, 16) for x in r[2].split(",")],
                        "s0": unhex(r[3]), "s2": unhex(r[4]), "s6": unhex(r[5])})
        elif r[0] == "S":
            out.append({"fmt": None, "s": unhex(r[1])})
    return out


def unhex(h: str) -> bytes:
    return b"" if h == "-" else bytes.fromhex(h)

