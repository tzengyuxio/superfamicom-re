"""Button scripts (tools/drive.py syntax, counted from frame 10) and memory addresses of the mahjong2 verifications.

Title -> start -> start (save slots; slot 1 is new) -> name entry: a (closes the hint), a (あ), down x6 right x12
(おわり), a -> おとこ (a) -> face (a) -> voice (a) -> はい (a) -> main menu (雀荘 大会 練習 / ルール ランク 成績 / 記録 勝利
終了) at ~4760 -> 雀荘 (a) -> あなたの家 (a) -> opponent cards at ~5420 -> リンカーン (a), ノストラダムス (right, a),
関羽 (right, a) -> はい, 半荘回数, レート, サシ馬 (a each) -> the table. On the table every a discards the drawn tile.
With this exact script the 14th press (frame 13840) makes リンカーン speak (his palette is loaded at 13992), and the
47th (frame 19780) leads to ノストラダムス's win (三暗刻, 立直, 門前清摸和, ドラ; 満貫).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools"))
from replay import end_frame, expand  # noqa: F401  (re-exported)

NAME_ENTRY = " ".join(["down:6 w20"] * 6 + ["right:6 w20"] * 12)
TO_MENU = ("w600 start:10 w200 start:10 w900 a:10 w100 a:10 w60 a:10 w60 " + NAME_ENTRY
           + " a:10 w500 a:10 w200 a:10 w200 a:10 w200 a:10 w600")                     # main menu at 4758
TO_PARLORS = TO_MENU + " a:10 w300"                                                    # 雀荘 selection
TO_CARDS = TO_PARLORS + " a:10 w300"                                                   # あなたの家: cards at 5420
TO_GAME = (TO_CARDS + " a:10 w200 right:6 w30 a:10 w200 right:6 w30 a:10 w200" + " a:10 w300" * 16)  # table at 11500
DIALOGUE = TO_GAME + " a:10 w150" * 13        # 13 discards; the 14th (frame 13840) leads to リンカーン's line
DIALOGUE_SAVE = 13835                         # savestate frame, before the 14th press
DIALOGUE_STEPS = "w5 a:10"                    # each run presses it itself: presses after the savestate are lost
DIALOGUE_SHOT = 260                           # frames after the savestate: the face is up (text still typing)
TEXT_SHOT = 320                               # all 24 codes are typed out (the window closes by ~400)

YAKU = TO_GAME + " a:10 w150" * 46
YAKU_SAVE = 19775
YAKU_STEPS = "w5 a:10"
YAKU_SHOT = 200
YAKU_COUNT = 0x41             # number of yaku shown; ids at $175F,Y, han at $1769,Y
YAKU_IDS = 0x175F

RULES_SAVE = 6900             # before $01:8F8A (frame 6942) sets up the rules of the game in $0E02
PARAMS_SAVE = 8350            # before $01:C999 (frame 8392) expands the four players' parameters to $13D9

SEAT_SLOT = 0x1998            # 4 seats -> slot (index into SLOT_PERSON)
SLOT_PERSON = 0x199E          # person in each slot (0 = the player)
LINE_BUF = 0x0EB1             # the line being shown: 24 codes stored backwards, then the face code at $0EC9
LINE_FACE = 0x0EC9
DIALOGUE_WRAM = 0x16000       # $7F:6000: the speaker's dialogue stream (offset in WRAM)
FACE_STREAM_WRAM = 0x11000    # $7F:1000: the speaker's face stream (offset in WRAM)
EXPR_VRAM = 0xDC60            # the image the line's face code selects (1568 bytes copied from the stream)
TALK_VRAM = 0xD940            # the talking face (one of images 0-2, 800 bytes)
FACE_CGRAM = 0x1E0            # CGRAM row 15 = sprite palette 7: the face palette
FACE_OAM_PAL = 7
BG_CHR = 0x8000               # BG tiles; font code c is tile 0x56 + 2c (top) / 0x57 + 2c (bottom), palette 3
TILEMAP = 0x0000              # BG tilemap of the table (32 x 32)
RULES = 0x0E02                # rules in force, one item per byte (44)
RULE_SETS = 0x192F            # the player's three rule sets (22 bytes each, from SRAM); set 0 is used
PARAM_BUF = 0x13D9            # expanded parameters (32 bytes per seat, from $13D9 + 0x80 downwards)
PARLOR = 0x1A01               # current parlor
PARAM = 0x7EFFC0              # scratch WRAM (0 in this game) for per-run parameters of the hooks

# Hooks. Per-run parameters (written to PARAM by a "wram" patch):
#   +0 = 1: speaker := +1 ($00:C318 reads the speaker's person from $199E,Y)
#   +2 = 1: face code := +3 ($00:C366 runs right after the line was copied to LINE_BUF)
#   +4 = 1: the 24 codes := +16..+39 (in reading order)
#   +5 = n > 0: at $00:E0DB (the yaku names are about to be drawn) n names := +48..
#   +6 = 1: parlor := +7 at $01:8F8E (after the player's rule set was loaded to $0E02)
#   +8 = 1: slots 1-3 := +9..+11 at $01:C999 (the parameters are about to be expanded)
HOOK_LUA = """
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
local function wr(a, v) emu.write(a, v, emu.memType.snesMemory) end
emu.addMemoryCallback(function()
  if rd(0x7EFFC0) == 1 then wr(0x199E + emu.getState()["cpu.y"], rd(0x7EFFC1)) end
end, emu.callbackType.exec, 0x00C318)
emu.addMemoryCallback(function()
  if rd(0x7EFFC2) == 1 then wr(0x0EC9, rd(0x7EFFC3)) end
  if rd(0x7EFFC4) == 1 then for k = 0, 23 do wr(0x0EC8 - k, rd(0x7EFFD0 + k)) end end
end, emu.callbackType.exec, 0x00C366)
emu.addMemoryCallback(function()
  local n = rd(0x7EFFC5)
  if n > 0 then wr(0x41, n); for k = 0, n - 1 do wr(0x175F + k, rd(0x7EFFF0 + k)) end end
end, emu.callbackType.exec, 0x00E0DB)
emu.addMemoryCallback(function()
  if rd(0x7EFFC6) == 1 then wr(0x1A01, rd(0x7EFFC7)) end
end, emu.callbackType.exec, 0x018F8E)
emu.addMemoryCallback(function()
  if rd(0x7EFFC8) == 1 then for k = 1, 3 do wr(0x199E + k, rd(0x7EFFC8 + k)) end end
end, emu.callbackType.exec, 0x01C999)
"""
