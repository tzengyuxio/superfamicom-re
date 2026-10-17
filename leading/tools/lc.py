"""Helpers for the leading verification scripts (used with the shared tools/replay.py).

Button scripts (tools/drive.py syntax, counted from frame 10) and Lua snippets that collect what the game does and
hand it back through replay's EXTRA_SHOT as one hex string (records separated by \\n):

  PRT_LUA   every formatted print: the entries of services 3C / 43 / 4F / 61 (va pointer at DP $54) and 55 (sprintf,
            at DP $58) of the dispatcher $00:8000 -> "P svc fmt-address fmt-text args(8 words) str(arg0)" (strings
            as hex). Hooking the entries, not $00:8000 itself, keeps Mesen fast (service 0F runs ~270k times).
            Define PRT_FILTER(fmt) in Lua to keep only some format addresses.

parse() turns the hex string back into records. EXTRA_RESET clears the collected records after each load.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))

# Title (start accepted from ~4200) -> NEW GAME -> scenario menu (answers from ~4860)
TO_SCENARIO_MENU = "w4200 start:10 w300 a:10 w300"
# scenario 1 + YES (the scenario is built at ~5550, $02:BF2B) -> players 1 -> format JVD + YES -> beginner grade ->
# names unchanged -> confirm; the 13 presses after that go through the opening reports and the 会長's speech
NEW_GAME = TO_SCENARIO_MENU + " a:10 w300 a:10 w300 a:10 w300 a:10 w300 a:10 w300 a:10 w300 a:10 w300 right:10 w60" \
    " a:10 w300 a:10 w300 a:10 w300"
CHAIRMAN = NEW_GAME + " a:10 w200" * 4           # the 会長's face is drawn at ~9335 ($01:A58F)
MAIN = NEW_GAME + " a:10 w200" * 14              # main screen (command menu) at ~11450
# main -> ... -> product sheet of format 0 slot 0 (hit 1bas) at ~13490
SHEET_STEPS = ("w100 right:10 w60 a:10 w300 a:10 w300 a:10 w300 b:10 w200 b:10 w200 b:10 w200 right:10 w60 "
               "a:10 w300 a:10 w300")

COLLECT_LUA = """
local REC = {}
function REC_ADD(s) if #REC < 4000 then REC[#REC + 1] = s end end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
function MEMSTR(a)
  local t = {}
  for i = 0, 63 do
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
local function prt(svc, vaddr)
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local function rw(a) return rd(a) | rd(a + 1) << 8 end
  local va = rw(vaddr)
  local fmt = rw(va) | rd(va + 2) << 16
  if PRT_FILTER and not PRT_FILTER(fmt) then return end
  local a = {}
  for i = 0, 7 do a[#a + 1] = string.format("%04x", rw(va + 4 + 2 * i)) end
  REC_ADD(string.format("P %02x %06x %s %s %s", svc, fmt, MEMSTR(fmt), table.concat(a, ","),
    MEMSTR(rw(va + 4) | rd(va + 6) << 16)))
end
-- the dispatcher copies its stack arguments to direct page $52.. and jumps through $00:97B3
emu.addMemoryCallback(function() prt(0x3C, 0x54) end, emu.callbackType.exec, 0x00AE9B)
emu.addMemoryCallback(function() prt(0x43, 0x54) end, emu.callbackType.exec, 0x00B64D)
emu.addMemoryCallback(function() prt(0x4F, 0x54) end, emu.callbackType.exec, 0x00B659)
emu.addMemoryCallback(function() prt(0x61, 0x54) end, emu.callbackType.exec, 0x00B668)
emu.addMemoryCallback(function() prt(0x55, 0x58) end, emu.callbackType.exec, 0x00B62F)
"""


def parse(raw: bytes) -> list[list[str]]:
    text = raw.decode("latin-1")
    return [line.split(" ") for line in text.split("\n") if line and line != "-"]


def sjis(h: str) -> str:
    return "" if h == "-" else bytes.fromhex(h).decode("cp932", "replace")


def prints(records: list[list[str]]) -> list[dict]:
    return [{"svc": int(r[1], 16), "addr": int(r[2], 16), "fmt": sjis(r[3]),
             "args": [int(x, 16) for x in r[4].split(",")], "s1": sjis(r[5])} for r in records if r[0] == "P"]
