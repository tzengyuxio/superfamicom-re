"""Button scripts (tools/drive.py syntax, counted from frame 10), WRAM addresses and Lua hooks of the yokoyama
verifications.

Boot: title (w1200) -> start -> a (ゲームスタート) -> a (新しく始める) -> scenario list (189 / 219, down for 219) ->
difficulty 1 2 3 (right to move) -> ruler (2 rows of 3; scenario 219: 曹操 孫権 劉備) -> opening text -> the map of
the first month (政略フェイズ). The scenario loader $01:D4A9 runs after the ruler is chosen.

On the map: a opens the country panel, then the command menu (開発 統治 租税 防災 情報 / 輸送 人事 同盟 政策);
right x4 = 情報 -> a -> 国 / 武将 -> right (武将), a -> "どの国の武将を" (the map cursor picks the country, here set
through $0113 / $0115) -> a, a -> country panel, list "どの武将の情報を" -> a (summary of the first officer) -> a
(the officer's detail screen: name, faction, reading, all fields, face).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
from replay import end_frame, expand  # noqa: F401  (re-exported)

TO_SCENARIOS = "w1200 start:10 w800 a:10 w300 a:10 w300"          # scenario list


def scenario(k: int, difficulty: int = 0, ruler: int = 0) -> str:
    """From the scenario list: scenario k (0 = 189, 1 = 219), difficulty 0-2 (shown 1-3), ruler menu item."""
    s = "a:10 w300" if k == 0 else "down:10 w60 a:10 w300"
    s += " right:6 w30" * difficulty + " a:10 w300"
    s += " right:6 w30" * (ruler % 3) + " down:6 w30" * (ruler // 3) + " a:10 w600"
    return s


# From power-on to the map of the first month (the player's turn), scenario 189 as 袁紹 / 219 as 曹操
TO_MAP = [TO_SCENARIOS + " " + scenario(0)
          + " a:10 w300 a:10 w300 a:10 w300 w300 a:10 w200 w300 a:10 w200 w300 a:10 w500",
          TO_SCENARIOS + " " + scenario(1) + " a:10 w300 a:10 w300 a:10 w300 w400 a:10 w400 a:10 w400 a:10 w400"]
# ... -> 情報 -> 武将: "どの国の武将をご覧になりますか？" (save here; the run sets the cursor and presses on)
TO_PICK_COUNTRY = [p + " w20 a:10 w100 a:10 w100 a:10 w100" + " right:6 w20" * 3 + " right:6 w40 a:10 w100"
                   " right:6 w40 a:10 w100" for p in TO_MAP]
# ... -> 情報 -> 国: "どの国の情報をご覧になりますか？" (save here; the run sets the cursor and presses on)
TO_PICK_INFO = [p + " w20 a:10 w100 a:10 w100 a:10 w100" + " right:6 w20" * 3 + " right:6 w40 a:10 w100 a:10 w100"
                for p in TO_MAP]
INFO_STEPS = "a:10 w100 a:10 w250"   # pick -> the country information screen
INFO_SHOT = 400
DETAIL_STEPS = "a:10 w100 a:10 w100 a:10 w150 a:10 w150 a:10 w250"   # country -> panel -> list -> summary -> detail
DETAIL_FROM = 470             # frame (after the savestate) of the last press: the detail screen is drawn after it
DETAIL_SHOT = 760             # frames after the savestate: detail screen complete
HOME = [(2, 47, 19), (11, 37, 27)]   # (country, x, y = rom.Rom.position): 冀州 of 袁紹 (189), 洛陽 of 曹操 (219)

CURSOR = 0x0113               # map cursor x ($0113) and y ($0115), pixels of the 256-wide map; country = >> 4
PLAYER = 0x0448               # player's faction
DIFFICULTY = 0x044A
SCENARIO = 0x011F
FACE_PERSON = 0x0139          # person whose face $00:8B4D builds
OAM_SHADOW = 0x2000           # OAM copy in WRAM ($7E:2000, 544 bytes, DMA'd every frame)
CGRAM_SHADOW = 0x0500         # CGRAM copy in WRAM
FACE_OBJ_VRAM = 0x0000        # byte address of the OBJ tiles on the detail screen

# Lua: log every code $00:8D60 prints from frame CODES_FROM on; EXTRA_SHOT hands them over (4 hex digits each)
CODES_LUA = """
local codes={}
local cf=0
CODES_FROM=CODES_FROM or 0
emu.addEventCallback(function() cf=cf+1 end, emu.eventType.endFrame)
for _,a in ipairs({0x008D60, 0x808D60}) do
  emu.addMemoryCallback(function()
    if cf>=CODES_FROM then codes[#codes+1]=string.format("%04x", emu.getState()["cpu.a"] & 0xFFFF) end
  end, emu.callbackType.exec, a)
end
function EXTRA_RESET() codes={}; cf=0 end
function EXTRA_SHOT() local s=table.concat(codes); codes={}; if s=="" then s="00" end; return s end
"""

# Lua: the CGRAM shadow ($0500, 512 bytes) the first time the map palette routine $05:81B1 has filled it, then
# the zoom matrix $DB (0x400 = 1/4 scale) and the month $0127
MAP_PALETTE_LUA = """
local pal="00"
for _,a in ipairs({0x0581EB, 0x8581EB}) do
  emu.addMemoryCallback(function()
    if pal~="00" then return end
    local s={}
    for i=0x500,0x6FF do s[#s+1]=string.format("%02x", emu.read(i, emu.memType.snesWorkRam, false)) end
    for _,i in ipairs({0xDB, 0xDC, 0x127, 0x128}) do
      s[#s+1]=string.format("%02x", emu.read(i, emu.memType.snesWorkRam, false))
    end
    pal=table.concat(s)
  end, emu.callbackType.exec, a)
end
function EXTRA_RESET() pal="00" end
function EXTRA_SHOT() local s=pal; pal="00"; return s end
"""



def loader_lua(addr: int) -> str:
    """Lua: dump WRAM $0800-$1E15 (persons, countries, factions) when the scenario loader reaches addr
    (rom.Rom.loader_done: after the difficulty-1 金 / 米 change, before the difficulty-3 change)."""
    return f"""
local dump="00"
for _,a in ipairs({{{addr & 0x7FFFFF}, {addr | 0x800000}}}) do
  emu.addMemoryCallback(function()
    local s={{}}
    for i=0x800,0x1E15 do s[#s+1]=string.format("%02x", emu.read(i, emu.memType.snesWorkRam, false)) end
    dump=table.concat(s)
  end, emu.callbackType.exec, a)
end
function EXTRA_RESET() dump="00" end
function EXTRA_SHOT() local s=dump; dump="00"; return s end
"""


def cursor_lua(k: int) -> str:
    """Lua for the boot of TO_PICK_COUNTRY[k]: put the map cursor on the player's country HOME[k] 5 frames after
    TO_MAP[k] (pressing a on the map does nothing unless the cursor is on a country)."""
    _, x, y = HOME[k]
    return f"""
local cur_f=0
emu.addEventCallback(function() cur_f=cur_f+1
  if cur_f=={end_frame(TO_MAP[k] + " w20") + 5} then
    local w=function(a, v) emu.write(a, v, emu.memType.snesWorkRam) end
    w(0x113, {(16 * x + 8) & 255}); w(0x114, {(16 * x + 8) >> 8})
    w(0x115, {(16 * y + 8) & 255}); w(0x116, {(16 * y + 8) >> 8})
  end
end, emu.eventType.endFrame)
"""


def codes(hexstr: bytes) -> list[int]:
    """EXTRA_SHOT bytes of CODES_LUA -> list of codes."""
    return [hexstr[i] << 8 | hexstr[i + 1] for i in range(0, len(hexstr) - 1, 2)]


def cursor_patch(x: int, y: int) -> list[tuple[int, bytes]]:
    """WRAM patch putting the map cursor on the country at map position (x, y) (rom.Rom.position)."""
    return [(CURSOR, (16 * x + 8).to_bytes(2, "little") + (16 * y + 8).to_bytes(2, "little"))]
