"""Button scripts (tools/drive.py syntax, counted from frame 10) and memory addresses of the mahjong verifications.

Title -> start (name entry) -> start (jumps to おわり) -> a (name "あ") -> 男 -> face: up, a (はい) -> main menu
-> 雀荘 (a) -> 織田信長 (a) -> 豊臣秀吉 (right, a) -> 徳川家康 (right, a) -> しょうぶする -> the table.
On the table every a discards the drawn tile; with this exact script the 10th press makes 豊臣秀吉 speak
(dialogue stream loaded at frame 6356, window complete by 6440, closed by ~6530).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
from replay import end_frame, expand  # noqa: F401  (re-exported)

TO_MENU = "w1500 start:10 w200 a:10 w40 start:10 w100 a:10 w200 up:10 w30 a:10 w200 a:10 w300"   # menu at ~2790
TO_JANSO = TO_MENU + " a:10 w300"                                                          # 雀荘 cards at ~3000
TO_TABLE = (TO_MENU + " a:10 w200 a:10 w100 right:10 w30 a:10 w100 right:10 w30 a:10 w100 a:10 w200 a:10 w200"
            " a:10 w300 a:10 w300")
DIALOGUE = TO_TABLE + " a:10 w150" * 9       # 9 discards; the 10th (frame 6279) leads to 秀吉's line
DIALOGUE_SAVE = 6200                          # savestate frame, before the 10th press
DIALOGUE_STEPS = "w79 a:10"                   # each run presses it itself: presses before the savestate are lost
DIALOGUE_SHOT = 240                           # frames after the savestate: the window is drawn (gone by ~330)

# 10 more discards, then the press at frame 8270 leads to 織田信長's win: the yaku screen (平和, ドラ) is up by 8450
YAKU = DIALOGUE + " a:10 w150" * 11
YAKU_SAVE = 8265
YAKU_STEPS = "w5 a:10"
YAKU_SHOT = 190
YAKU_COUNT = 0x37             # number of yaku shown; ids at $071E,Y, han at $0728,Y
YAKU_IDS = 0x071E

SEAT_PERSON = 0x1C02          # 4 seats: person number (0x15+ = the player)
LINE_BUF = 0x04DE             # the line being shown: 16 codes stored backwards, then the face code at $04EE
LINE_FACE = 0x04EE
DIALOGUE_WRAM = 0x1F400       # $7F:F400: the speaker's dialogue stream (offset in WRAM)
FACE_STREAM_WRAM = 0x11000  # $7F:1000: the speaker's face stream (offset in WRAM)
EXPR_VRAM = 0xE400            # sprite tiles 0x120..: the image the line's face code selects (1568 bytes)
FACE_VRAM = 0xEA20            # sprite tiles 0x151.. (OBJ base $C000): the face next to the line
FACE_CGRAM = 0x120            # sprite palettes 1 and 2 (CGRAM rows 9 and 10) = the two face palettes
TEXT_ROWS = 15                # BG1 tilemap rows 15-18, columns 20-27: the two text lines (8x16 per code)
TEXT_COL = 20
BG1_CHR = 0x8000              # BG1 tiles; code c is drawn with tiles 0x6E + 2c (top) and 0x6F + 2c (bottom)
PARAM = 0x7EFFC0              # scratch WRAM (always 0 in this game) for per-run parameters of the hooks

# Hooks: $00:AB7C reads the speaker's person number ($1C03,X) to load his face stream; $00:ABB4 runs right after
# the line was copied to LINE_BUF. Per-run parameters (written to PARAM by a "wram" patch):
#   +0 = 1: speaker := +1;  +2 = 1: face code := +3;  +4 = 1: 16 codes := +16..+31 (in reading order)
#   +5 = n > 0: at $00:C37A (the yaku names are about to be drawn) n yaku := +32..
HOOK_LUA = """
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
local function wr(a, v) emu.write(a, v, emu.memType.snesMemory) end
emu.addMemoryCallback(function()
  if rd(0x7EFFC0) == 1 then wr(0x1C03 + emu.getState()["cpu.x"], rd(0x7EFFC1)) end
end, emu.callbackType.exec, 0x00AB7C)
emu.addMemoryCallback(function()
  if rd(0x7EFFC2) == 1 then wr(0x04EE, rd(0x7EFFC3)) end
  if rd(0x7EFFC4) == 1 then for k = 0, 15 do wr(0x04ED - k, rd(0x7EFFD0 + k)) end end
end, emu.callbackType.exec, 0x00ABB4)
emu.addMemoryCallback(function()
  local n = rd(0x7EFFC5)
  if n > 0 then wr(0x37, n); for k = 0, n - 1 do wr(0x071E + k, rd(0x7EFFE0 + k)) end end
end, emu.callbackType.exec, 0x00C37A)
"""


def le16(v: int) -> bytes:
    return bytes((v & 0xFF, v >> 8 & 0xFF))
