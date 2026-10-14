"""Helpers for the airmanage2 verification scripts (used with the shared tools/replay.py).

Button scripts (tools/drive.py syntax, counted from frame 10), memory addresses, and Lua snippets that collect
what the game does and hand it back through replay's EXTRA_SHOT as one hex string (records separated by \\n):

  PRT_LUA   every formatted print: service 3C / 43 / 4F / 61 (va pointer at S+6) and 55 (sprintf, at S+10) of the
            dispatcher $00:8000 -> "P svc fmt-text args(8 words) str(arg0) str(arg2)" (strings as hex)
  FACE_LUA  every face draw ($04:8199 / $84:8199, descriptor pointer at S+$286) -> "F kind image palette"

parse() turns the hex string back into records. EXTRA_RESET clears the collected records after each load.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))

# Title -> NEW GAME -> scenario menu (shown from ~3100) -> scenario + YES (game state built at ~3397) ->
# difficulty -> players -> area menu (~4001) -> home city (~4355) -> confirm -> setup screen -> start.
TO_SCENARIO_MENU = "w2690 start:10 w200 a:10 w200"          # ends at frame 2930 + 30; menu answers from ~3100
SCENARIO_MENU_FRAME = 3100
TO_AREA_MENU = TO_SCENARIO_MENU + " a:10 w200 a:10 w200 a:10 w300 a:10 w300"     # area menu at frame ~4280
AREA_MENU_FRAME = 4250
AREA_KEYS = ["", "down:10 w40", "right:10 w40", "right:10 w40 right:10 w40", "right:10 w40 right:10 w40 down:10 w40",
             "right:10 w40 right:10 w40 right:10 w40", "right:10 w40 right:10 w40 right:10 w40 down:10 w40"]
# Scenario 1, Europe, Berlin (the cursor is moved onto it), everything else default; the COM players' turn
# ends on the world map; the press at 7886 starts the player's turn, whose first secretary message draws her
# face (descriptor $28C5) at ~7963.
BOOT = (TO_AREA_MENU + " a:10 w300 up:45 w30 left:3 w30 right:3 w20 a:10 w201 a:10 w201 a:10 w201 a:10 w201 "
        "a:10 w301 a:10 w1800")
BOOT_FACE = BOOT + " a:10 w150"
FACE_SAVE_FRAME = 7900
# + 8 messages -> main screen; 4 x right -> aircraft icon; a -> maker menu; a -> first maker (ビッカ－ス in
# scenario 1): the spec screen prints the aircraft record at WRAM $3DC0 at ~10808
MAIN = BOOT + " a:10 w150" * 8 + " a:10 w300"
SPEC = MAIN + " w100" + " right:10 w60" * 4 + " a:10 w600 a:10 w400"
SPEC_SAVE_FRAME = 10790

CURSOR_X, CURSOR_Y = 0x24CD, 0x24CF        # area map cursor (LE16), = OAM $0900 / $0901
PLAYER = 0x2541                            # 4 x 35 bytes; +1 home city
SECRETARY = 0x28C5                         # 4 x 4-byte face descriptors
STAFF = 0x28D5                             # 4 players x 4 staff x 4-byte descriptors
AIRCRAFT_LIST_INDEX = 0x3D37               # on-sale list: aircraft numbers, records at $3D47 + 11 * slot
AIRCRAFT_LIST = 0x3D47
SPEC_SLOT = 11                             # the spec screen's record ($3DC0) in the run above

COLLECT_LUA = """
local REC = {}
function REC_ADD(s) if #REC < 4000 then REC[#REC + 1] = s end end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
local function rw(a) return rd(a) | rd(a + 1) << 8 end
function MEMSTR(a)
  local t = {}
  for i = 0, 47 do
    local c = rd(a + i)
    if c == 0 then break end
    t[#t + 1] = string.format("%02x", c)
  end
  return #t > 0 and table.concat(t) or "-"
end
function EXTRA_RESET() REC = {} end
function EXTRA_SHOT()
  local s = "-\\n" .. table.concat(REC, "\\n")    -- never empty: replay drops an empty last field
  return (s:gsub(".", function(c) return string.format("%02x", c:byte()) end))
end
"""

PRT_LUA = """
emu.addMemoryCallback(function()
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local function rw(a) return rd(a) | rd(a + 1) << 8 end
  local s = emu.getState()["cpu.sp"]
  local svc = rd(s + 4)
  local va
  if svc == 0x3C or svc == 0x43 or svc == 0x4F or svc == 0x61 then va = rw(s + 6)
  elseif svc == 0x55 then va = rw(s + 10)
  else return end
  local fmt = rw(va) | rd(va + 2) << 16
  local a = {}
  for i = 0, 7 do a[#a + 1] = string.format("%04x", rw(va + 4 + 2 * i)) end
  REC_ADD(string.format("P %02x %s %s %s %s", svc, MEMSTR(fmt), table.concat(a, ","),
    MEMSTR(rw(va + 4) | rd(va + 6) << 16), MEMSTR(rw(va + 8) | rd(va + 10) << 16)))
end, emu.callbackType.exec, 0x008000)
"""

FACE_LUA = """
local function face_hook()
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local s = emu.getState()["cpu.sp"]
  local p = rd(s + 0x286) | rd(s + 0x287) << 8 | rd(s + 0x288) << 16
  REC_ADD(string.format("F %d %d %d", rd(p) | rd(p + 1) << 8, rd(p + 2), rd(p + 3)))
end
emu.addMemoryCallback(face_hook, emu.callbackType.exec, 0x848199)
emu.addMemoryCallback(face_hook, emu.callbackType.exec, 0x048199)   -- some callers JSL $04:8000
"""


def parse(raw: bytes) -> list[list[str]]:
    """Records of one run's EXTRA_SHOT (the last read of replay's result)."""
    text = raw.decode("latin-1")
    return [line.split(" ") for line in text.split("\n") if line and line != "-"]


def sjis(h: str) -> str:
    """A hex string from MEMSTR as text ("-" = empty)."""
    if h == "-":
        return ""
    return bytes.fromhex(h).decode("cp932", "replace")


def prints(records: list[list[str]]) -> list[dict]:
    out = []
    for r in records:
        if r[0] == "P":
            out.append({"svc": int(r[1], 16), "fmt": sjis(r[2]), "args": [int(x, 16) for x in r[3].split(",")],
                        "s1": sjis(r[4]), "s2": sjis(r[5])})
    return out


def faces(records: list[list[str]]) -> list[tuple[int, int, int]]:
    return [(int(r[1]), int(r[2]), int(r[3])) for r in records if r[0] == "F"]


def le16(v: int) -> bytes:
    return bytes((v & 0xFF, v >> 8 & 0xFF))
