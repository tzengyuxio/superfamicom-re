"""Button scripts, pointer writes and Lua hooks of the tenbu verifications.

The game is driven with its pointer (OAM sprite 0, WRAM $0200 = X, $0201 = Y): a step "p:x:y" writes the pointer
one frame after its frame and waits 4 frames; the other steps are tools/replay.py steps (button[:hold], wN).
tools/replay.py cannot write WRAM at a frame, so split() turns the pointer steps into waits plus a list of writes
that pointer_lua() performs from an endFrame callback (its own frame counter, set to the savestate frame by
EXTRA_RESET). Inside pull-down menus a pointer write needs a d-pad nudge (NUDGE) before B is accepted.

Boot: title (PUSH ANY BUTTON: three STARTs) -> 新規 (90, 128) -> scenario list (SCENARIO_Y) -> opening text (了 at
(118, 212)) -> 諸侯を選択して下さい (the ruler list, row r at (197, 101 + 19 r)) -> ruler card (了 (120, 186)) -> 難易度
(普 (128, 137)) -> confirm (了 (121, 160)) -> the map. The scenario loader $00:CA31 runs after the 了 of the opening
text, again when a ruler is clicked (the ruler card is drawn from this load) and once more when the game starts.
Take savestates on a settled screen (the boot scripts end with w200): a state saved during a screen change breaks
the game after it is loaded.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
from replay import end_frame, expand

NUDGE = "right:4 left:4 down:4 up:4"
TO_SCENARIOS = "w440 start:10 w300 start:10 w500 start:10 w500 w30 p:90:128 b:10 w300 w200"
SCENARIO_Y = [82, 105, 128, 156]
RULER_X, RULER_Y0, RULER_DY = 197, 101, 19   # ruler list row r: pointer (197, 101 + 19 r)


def to_rulers(k: int) -> str:
    """From the scenario list: scenario k, through the opening text, to the ruler list."""
    return f"p:128:{SCENARIO_Y[k]} b:10 w300 w100 p:118:212 b:10 w300 w300"


def card(row: int = 0) -> str:
    """From the ruler list: click ruler row `row` (the card appears)."""
    return f"p:{RULER_X}:{RULER_Y0 + RULER_DY * row} b:10 w300"


START = "p:120:186 b:10 w300 p:128:137 b:10 w300 p:121:160 b:10 w300 w600"   # card -> 普 -> confirm -> map
# The game runs with NMI off after the boot logo ($4200 = 01 from frame 362): savestates are taken and loaded in
# the vblank wait $00:AD96 (polls $4212), at its RTS
FRAME_HOOK = 0x00ADA2
# On the map the game turns NMI back on ($4200 = B1) and no longer waits in $00:AD96: savestates taken on the map
# use tools/replay.py's default hook (the NMI handler)
MAP_HOOK = None
# On the map: icon 2 (32, 12) -> 武将情報検索 (40, 80): the list window (州 / 郡国 / 勢力 / 武将), 幽州 selected
OPEN_PERSONS = f"p:32:12 right:4 left:4 b:10 w60 p:40:80 {NUDGE} b:10 w300 w200"
MAILBOX = 0x17E00             # WRAM $7F:7E00: unused in every dump, hands per-run values to the Lua hooks


def split(steps: str, start: int = 10) -> tuple[str, list[tuple[int, int, int]]]:
    """Steps with p:x:y -> (replay steps with the pointer steps as w4, [(frame, x, y)])."""
    out, writes, f = [], [], start
    for st in expand(steps).split():
        if st.startswith("p:"):
            _, x, y = st.split(":")
            writes.append((f + 1, int(x), int(y)))
            out.append("w4")
            f += 4
        else:
            out.append(st)
            f = end_frame(st, f)
    return " ".join(out), writes


def pointer_lua(boot_writes, run_writes: list, save: int) -> str:
    """Lua: pointer writes at absolute frames before the savestate, and in run i (WRAM MAILBOX = i, LE16, written
    by the run's "wram" patch) at save + frame. POINTER_RESET() must be called from EXTRA_RESET."""
    b = ",".join(f"{{{f},{x},{y}}}" for f, x, y in boot_writes)
    r = ",".join("{" + ",".join(f"{{{save + f},{x},{y}}}" for f, x, y in w) + "}" for w in run_writes)
    return f"""
local PB={{{b}}}
local PR={{{r}}}
local pw, pf = PB, 0
emu.addEventCallback(function()
  pf=pf+1
  for _,e in ipairs(pw) do
    if e[1]==pf then
      emu.write(0x200,e[2],emu.memType.snesWorkRam); emu.write(0x201,e[3],emu.memType.snesWorkRam)
    end
  end
end, emu.eventType.endFrame)
function POINTER_RESET()
  local i=emu.read({MAILBOX},emu.memType.snesWorkRam,false)+256*emu.read({MAILBOX + 1},emu.memType.snesWorkRam,false)
  pw=PR[i+1] or {{}}; pf={save}
end
function PFRAME() return pf end
"""


def prepare(boot: str, run_steps: list[str]) -> tuple[str, int, list[str], str]:
    """(replay boot steps, save frame, replay steps of each run, pointer Lua) for a boot script and run steps."""
    boot_r, bw = split(boot, 10)
    save = end_frame(boot_r, 10)
    runs = [split(st, 0) for st in run_steps]
    return boot_r, save, [r for r, _ in runs], pointer_lua(bw, [w for _, w in runs], save)


def mail(i: int, extra: bytes = b"") -> tuple[int, bytes]:
    """WRAM patch for run i: the run index (LE16) and extra bytes at MAILBOX + 2."""
    return MAILBOX, bytes([i & 255, i >> 8]) + extra


# Lua: log every A of the glyph put $00:A0CA (tile code | flags) from frame CODES_FROM after the savestate on
CODES_LUA = """
local codes={}
local cf=-1
emu.addMemoryCallback(function()
  if cf>=CODES_FROM then codes[#codes+1]=string.format("%04x", emu.getState()["cpu.a"] & 0xFFFF) end
end, emu.callbackType.exec, 0x00A0CA)
emu.addEventCallback(function() if cf>=0 then cf=cf+1 end end, emu.eventType.endFrame)
CODES_START=function() codes={}; cf=0 end
CODES_TAKE=function() local s=table.concat(codes); codes={}; if s=="" then s="00" end; return s end
"""


def codes(raw: bytes) -> list[int]:
    return [raw[i] << 8 | raw[i + 1] for i in range(0, len(raw) - 1, 2)]
