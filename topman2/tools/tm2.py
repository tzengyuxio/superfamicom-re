"""Helpers for the topman2 verification scripts (used with the shared tools/replay.py).

Button scripts (tools/drive.py syntax, counted from frame 10), WRAM addresses, and Lua snippets that collect what
the game does and hand it back through replay's EXTRA_SHOT as one hex string (records separated by \\n):

  TEXT_LUA  every string drawn by the text routine $01:9392 (string pointer at S+6) -> "T <hex>"
  FACE_LUA  every call of the file-graphics routine $01:B0D8 for a face file -> "F <name ptr> <frame> <x> <y>"

PARAM ($7E:E000, zero in every dump of the game) carries per-run values to the Lua hooks; the boot (before
~frame 650) clears it, so a savestate taken earlier must copy it into Lua in EXTRA_RESET (verify_companies.py).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))

# Title (START) -> NEW GAME -> PRESENT MODE -> scenario menu (the secretary's first face at ~1598)
TITLE = "w1300 start:10 w200"
TO_SCENARIO_MENU = TITLE + " a:10 w200 a:10 w300"
# scenario chosen, page shown, YES, company page, OK, name page, OK, level, OK -> confirm page; the last A starts
# the game (the population record is copied to $4417 at ~4750 for scenario 1)
SETUP_AFTER_SCENARIO = " a:10 w300" * 8
PARAM = 0xE000

COLLECT_LUA = """
local REC = {}
function REC_ADD(s) if #REC < 3000 then REC[#REC + 1] = s end end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
function MEMSTR(a)
  local t = {}
  for i = 0, 200 do
    local c = rd(a + i)
    if c == 0 then break end
    t[#t + 1] = string.format("%02x", c)
  end
  return #t > 0 and table.concat(t) or "-"
end
function EXTRA_RESET() REC = {} end
function EXTRA_SHOT()
  local s = "-\\n" .. table.concat(REC, "\\n")
  return (s:gsub(".", function(c) return string.format("%02x", c:byte()) end))
end
"""

TEXT_LUA = """
local function text_hook()
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local s = emu.getState()["cpu.sp"]
  REC_ADD("T " .. MEMSTR(rd(s + 6) | rd(s + 7) << 8 | rd(s + 8) << 16))
end
emu.addMemoryCallback(text_hook, emu.callbackType.exec, 0x019392)
emu.addMemoryCallback(text_hook, emu.callbackType.exec, 0x819392)
"""

FACE_LUA = """
local function face_hook()
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local s = emu.getState()["cpu.sp"]
  local p = rd(s + 4) | rd(s + 5) << 8
  if p >= 0xD36B and p <= 0xD3AE then
    REC_ADD(string.format("F %04x %d %d %d", p, rd(s + 18), rd(s + 10), rd(s + 12)))
  end
end
emu.addMemoryCallback(face_hook, emu.callbackType.exec, 0x01B0D8)
emu.addMemoryCallback(face_hook, emu.callbackType.exec, 0x81B0D8)
"""


def parse(raw: bytes) -> list[list[str]]:
    text = raw.decode("latin-1")
    return [line.split(" ") for line in text.split("\n") if line and line != "-"]


def sjis(h: str) -> str:
    return "" if h == "-" else bytes.fromhex(h).decode("cp932", "replace")


def texts(records: list[list[str]]) -> list[str]:
    return [sjis(r[1]) for r in records if r[0] == "T"]


def faces(records: list[list[str]]) -> list[tuple[int, int, int, int]]:
    return [(int(r[1], 16), int(r[2]), int(r[3]), int(r[4])) for r in records if r[0] == "F"]


def le16(v: int) -> bytes:
    return bytes((v & 0xFF, v >> 8 & 0xFF))
