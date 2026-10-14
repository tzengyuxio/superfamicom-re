"""Helpers for the verification scripts: talk to the game's p-code VM from Mesen Lua (used with tools/replay.py).

The game is C compiled to KOEI's p-code. The VM keeps its PC in direct page $06-$08 and fetches the next opcode
at $00:A410 (LDA [$06],Y); calls go through JML into the callee, whose first bytes are native code (JSR $1BE2),
so a p-code function at WRAM address a can be hooked with an exec callback on $7E:a. On entry the arguments
are on the native stack: S+8 = first argument, S+10 = second, ... (S+1..7: return addresses and the caller's PC).

INJECT_LUA: when a run sets the flag byte at FLAG (through a replay "wram" patch) and the VM is about to execute
the opcode at the p-code address in INJECT_AT, the PC is pointed at a stub written to STUB (also through the
"wram" patch). Stubs are built with stub(): they push arguments, call a function and jump back, so the game runs
its own code on values we choose (a city index, an aircraft index, ...).

PRINTF_LUA: logs every call of the game's printf-like functions ($1129, $1139, $1149: fmt, args...) with the format
pointer, 6 argument words, the format string and the strings at the first two arguments. EXTRA_SHOT hands them
back to replay(); parse with printf_records().
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))

# New game, scenario s, PLAYER1 = MAN, home city London (the cursor is written next to it at frame 3680 and the
# "left" press makes the game hit-test it; it only hit-tests after a d-pad press), company name, COM names,
# difficulty and confirmation left at their defaults. The main screen's command loop runs from about frame 9080.
BOOT = ("w2400 start:10 w200 a:10 {scenario} a:10 w200 a:10 w100 down:10 w100 a:10 w300 w30 left:1 w20 a:10 "
        "w200 a:10 w200 a:10 w200 a:10 w200 a:10 w300")
SCENARIO_KEYS = ["w200", "w170 down:10"]   # same timing either way
MAIN_FRAME = 9300
BOOT_LUA = """
local _f = 0
function FRAME() return _f end
emu.addEventCallback(function()
  _f = _f + 1
  if _f == 3680 then
    emu.write(%(cursor)d, 18, emu.memType.snesWorkRam)
    emu.write(%(cursor)d + 2, 50, emu.memType.snesWorkRam)
  end
end, emu.eventType.endFrame)
"""
HOME = 11              # London

# Addresses of the original release, and what Rev 1 adds: ALNMAIN's data and the WRAM variables after it move
# by +6; COMMAND code moves by +$11 ($961E) / +$28 ($A319 and later); TRADE, DIORMINF, COMMON and bank 0 do not.
ADDR = {
    "cursor": 0x480E,           # WRAM: home-city / map cursor x (y at +2)
    "scroll": 0x480C,           # WRAM: main map scroll x
    "scenario": 0x4686,         # WRAM: scenario 0 / 1
    "city_rec": 0x5BF2,         # WRAM: 22 x 12 bytes
    "slot_rec": 0x6DD6,         # WRAM: 22 x 20 bytes
    "player_rec": 0x6CD6,       # WRAM: 4 x 64 bytes
    "face_desc": 0x7146,        # WRAM: 4 x 4 bytes, the players' aides
    "partners": 0x7156,         # WRAM: 4 x 3 x 4 bytes, negotiation partners
    "command_loop": 0x962E,     # COMMAND $961E: the main screen's pad wait loop (push 0 / push 3 / call $156F)
    "command_guard": 0x9629,    # COMMAND byte 0x89 there (tells COMMAND from the modules loaded over it)
    "city_show": 0xAA02,        # COMMAND: load DIORAMA + DIORMINF and show city (city, player)
    "distance_box": 0xA319,     # COMMAND: (a, b) prints "%5u0km" with distance [b][a]
    "trade_name": 0xBDE9,       # COMMAND: "TRADE"
    "km_fmt": 0xBE57,           # COMMAND: "%5u0km"
}
REV1_SHIFT = {"cursor": 6, "scroll": 6, "scenario": 6, "city_rec": 6, "slot_rec": 6, "player_rec": 6,
              "face_desc": 6, "partners": 6, "command_loop": 0x11, "command_guard": 0x11, "city_show": 0x28,
              "distance_box": 0x28, "trade_name": 0x28, "km_fmt": 0x28}


def addresses(rev: int) -> dict:
    return {k: v + (REV1_SHIFT.get(k, 0) if rev else 0) for k, v in ADDR.items()}


def boot(scenario: int) -> str:
    return BOOT.format(scenario=SCENARIO_KEYS[scenario])


def boot_lua(rev: int) -> str:
    return BOOT_LUA % {"cursor": addresses(rev)["cursor"]}


def command_inject(rev: int, calls: list[tuple[int, list[int]]]) -> list[tuple[int, bytes]]:
    """inject() at the main screen's pad loop."""
    a = addresses(rev)
    return inject(calls, a["command_loop"], (a["command_guard"], 0x89))


STUB = 0x1F00          # $7E:1F00-$7E:1FEF: between COMMON ($1000-$1ECF) and ALNMAIN ($2000); never written
FLAG = 0x1FF0          # 1 = inject once
INJECT_AT = 0x1FF2     # LE16 p-code address where the stub is entered; the stub jumps back there
GUARD = 0x1FF4         # LE16 address + byte that must be in WRAM there (which module is loaded)

INJECT_LUA = """
local function wr(a) return emu.read(a, emu.memType.snesWorkRam) end
local function ww(a) return wr(a) | wr(a + 1) << 8 end
emu.addMemoryCallback(function()
  if wr(FLAG) ~= 1 then return end
  if ww(6) ~= ww(INJECT_AT) or wr(8) ~= 0x7E then return end
  if wr(ww(GUARD)) ~= wr(GUARD + 2) then return end
  emu.write(FLAG, 0, emu.memType.snesWorkRam)
  INJECTED = true
  emu.write(6, STUB & 0xFF, emu.memType.snesWorkRam)
  emu.write(7, STUB >> 8, emu.memType.snesWorkRam)
end, emu.callbackType.exec, 0x00A410)
""".replace("INJECT_AT", str(INJECT_AT)).replace("FLAG", str(FLAG)).replace("GUARD", str(GUARD)).replace(
    "STUB", str(STUB))

PRINTF_LUA = """
local pf = {}
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
local function rw(a) return rd(a) | rd(a + 1) << 8 end
local function str(a)
  local t = {}
  for i = 0, 31 do
    local c = (a ~= 0) and rd(0x7E0000 + a + i) or 0
    if c == 0 then for _ = i, 31 do t[#t + 1] = "00" end break end
    t[#t + 1] = string.format("%02x", c)
  end
  return table.concat(t)
end
local function hook()
  if not INJECTED then return end
  local s = emu.getState()["cpu.sp"]
  local h = {string.format("%02x%02x", rd(s + 8), rd(s + 9))}
  for i = 0, 5 do h[#h + 1] = string.format("%02x%02x", rd(s + 10 + 2 * i), rd(s + 11 + 2 * i)) end
  h[#h + 1] = str(rw(s + 8))
  h[#h + 1] = str(rw(s + 10))
  h[#h + 1] = str(rw(s + 12))
  if #pf < 400 then pf[#pf + 1] = table.concat(h) end
end
emu.addMemoryCallback(hook, emu.callbackType.exec, 0x7E1129)
emu.addMemoryCallback(hook, emu.callbackType.exec, 0x7E1139)
emu.addMemoryCallback(hook, emu.callbackType.exec, 0x7E1149)
function EXTRA_RESET() pf = {}; INJECTED = false end
function EXTRA_SHOT() return table.concat(pf) end
"""
RECORD = 2 + 12 + 96


def stub(calls: list[tuple[int, list[int]]], back: int) -> bytes:
    """p-code that calls each (function, [first arg, second, ...]) and then jumps to back."""
    out = bytearray()
    for func, args in calls:
        for a in reversed(args):
            out += bytes([0x8E, a & 0xFF, a >> 8 & 0xFF])  # push imm16
        out += bytes([0xE9, func & 0xFF, func >> 8, 2 * len(args)])  # call, pop
    out += bytes([0xD6, back & 0xFF, back >> 8])  # jmp
    assert len(out) <= FLAG - STUB, len(out)
    return bytes(out)


def inject(calls: list[tuple[int, list[int]]], at: int, guard: tuple[int, int]) -> list[tuple[int, bytes]]:
    """replay "wram" patches that make the VM run the stub once when it reaches p-code address at, provided
    WRAM[guard[0]] == guard[1]."""
    return [(STUB, stub(calls, at)), (INJECT_AT, at.to_bytes(2, "little")),
            (GUARD, guard[0].to_bytes(2, "little") + bytes([guard[1]])), (FLAG, b"\x01")]


def printf_records(raw: bytes) -> list[dict]:
    out = []
    for i in range(0, len(raw) - RECORD + 1, RECORD):
        r = raw[i:i + RECORD]

        def s(k, r=r):
            b = r[14 + 32 * k:14 + 32 * k + 32]
            return b.split(b"\0")[0].decode("cp932", "replace")
        out.append({"fmt_ptr": int.from_bytes(r[:2], "little"),
                    "args": [int.from_bytes(r[2 + 2 * j:4 + 2 * j], "little") for j in range(6)],
                    "fmt": s(0), "s0": s(1), "s1": s(2)})
    return out
