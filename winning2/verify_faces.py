#!/usr/bin/env python3
"""Check the faces in Mesen: the game's dialog face ($CC:0C67(..., id, kind)) is forced to every kind / id, and
the face it decompresses and the palette it loads must be rom.face_bytes / face_palette_number of rom.face_code.

From a savestate before the secretary's first dialog face (tools/w2.py new_game + 60 presses; the face is drawn
after the second press, ~270 frames later), a hook on $CC:0C67 replaces kind and id. The year (WRAM $7E:8583)
and, for jockeys, the age byte (+4 of the jockey record) are patched so that every face code is reached once
(208 runs: secretaries at year 0 and 15, jockeys 0-60 at age 20 and 40, the women jockeys' slots at the years
that show them, trainers and their successors by year, owners, kinds 5 / 7 / 10). When the dialog loads the palette
($C1:0CCF called from $CC:0FA3) the Lua reads the palette pointer ($C1:E52D + 32 p) and the 960 bytes the face
loader ($C1:0F6B) decompressed to $7F:8000.

Program '96 (dialog $C8:0C67, palette $CC:0CAD from $C8:1139, year $8586): 234 runs for its 235 face codes (all but
104 / 105, jockey 46's own faces, which it never shows; see rom.face_code).

Usage: .venv/bin/python winning2/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import w2  # puts tools/ on sys.path
from replay import end_frame, replay
from rom import (
    DEFAULT_ROM,
    FACE_BYTES,
    JOCKEY_COUNT,
    JOCKEY_NEW_FACE_96,
    JOCKEY_SIZE,
    ROM_JOCKEY_COUNT,
    TRAINER_SUCCESSOR,
    TRAINER_SUCCESSOR_96,
    Rom,
    face_code,
    face_palette_number,
)

ADDR = {
    "original": {"dialog": 0xCC0C67, "palette": 0xC10CCF, "palette_ret": 0xCC0FA6, "palette_base": 0xC1E52D,
                 "year": 0x8583, "jockey": 0x9D58},
    # Program '96: the same dialog function at $C8:0C67, palette loader $CC:0CAD called from $C8:1139, WRAM + 3
    "program96": {"dialog": 0xC80C67, "palette": 0xCC0CAD, "palette_ret": 0xC8113C, "palette_base": 0xCAE939,
                  "year": 0x8586, "jockey": 0x9CE7},
}

LUA = """
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
local function wr(a, v) emu.write(a, v, emu.memType.snesMemory) end
local done = false
RESET_HOOKS[#RESET_HOOKS + 1] = function() done = false end
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  wr(sp + 10, PARAM(1)); wr(sp + 11, PARAM(2)); wr(sp + 12, PARAM(0)); wr(sp + 13, 0)
end, emu.callbackType.exec, @DIALOG@)
emu.addMemoryCallback(function()
  if done then return end
  local sp = emu.getState()["cpu.sp"]
  if (rd(sp + 1) | rd(sp + 2) << 8 | rd(sp + 3) << 16) ~= @RET@ then return end
  done = true
  local t = {string.format("%02x%02x%02x", rd(sp + 10), rd(sp + 9), rd(sp + 8))}
  for i = 0, @N@ - 1 do t[#t + 1] = string.format("%02x", rd(0x7F8000 + i)) end
  REC_ADD(table.concat(t))
end, emu.callbackType.exec, @PALETTE@)
"""


def cases(rom: Rom) -> list[tuple[int, int, int, int | None]]:
    """(kind, id, year, jockey age or None) covering every face code once (Program '96: all but 104 / 105, jockey
    46's own faces, which the game never shows)."""
    out = [(1, i, y, None) for i in range(6) for y in (0, 15)]
    if rom.version == "program96":
        for i in range(61):
            if i != 0x2E:
                y = 16 if i in (8, 14, 0x38) else 0
                out += [(2, i, y, 20), (2, i, y, 40)]
        out += [(2, 8, 0, None), (2, 14, 0, None), (2, 0x2E, 0, None), (2, 0x2E, 14, None), (2, 0x38, 0, None),
                (2, 0x13, 8, None), (2, 0x1A, 13, None), (2, 0x1D, 14, None), (2, 0x2A, 22, None)]
        # jockey 19 (0x13) is a woman jockey slot from year 8 to 22
        out += [(2, j, 23 if j == 0x13 else y, a) for j, y in JOCKEY_NEW_FACE_96 for a in (20, 40)]
        out += [(2, 0xFFFE, 0, 20)]
        out += [(3, i, 0, None) for i in range(20)] + [(3, i, y, None) for i, (y, _) in TRAINER_SUCCESSOR_96.items()]
    else:
        for i in range(61):
            y = 20 if i in (0x38, 0x19) else 0
            out += [(2, i, y, 20), (2, i, y, 40)]
        out += [(2, 0x38, 0, None), (2, 0x19, 0, None), (2, 0x38, 8, None), (2, 0x19, 10, None),
                (2, 0x32, 16, None), (2, 0x11, 24, None)]
        out += [(3, i, 0, None) for i in range(20)]
        out += [(3, i, y, None) for i, lst in TRAINER_SUCCESSOR.items() for y, _ in lst]
    out += [(4, i, 0, None) for i in range(28)] + [(5, i, 0, None) for i in range(5)]
    out += [(7, 0, 0, None), (10, 0, 0, None), (10, 1, 0, None)]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像（種類／編號 → 圖與調色盤）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    if rom.version not in ADDR:
        raise SystemExit(f"{rom.version}: addresses not known")
    a = ADDR[rom.version]
    t0 = time.time()
    runs, expect = [], []
    for kind, i, year, age in cases(rom):
        wram = [(w2.WRAM_PARAM, bytes([kind, i & 0xFF, i >> 8])), (a["year"], bytes([year]))]
        patch = []
        if kind == 2 and age is not None and i < JOCKEY_COUNT + ROM_JOCKEY_COUNT:
            if i < JOCKEY_COUNT:
                b = rom.jockey_record(i)
                wram.append((a["jockey"] + JOCKEY_SIZE * i + 4, bytes([b[4] & 0x80 | age])))
            else:
                o = rom.o["ROM_JOCKEY"] + JOCKEY_SIZE * (i - JOCKEY_COUNT) + 4
                patch.append((o, bytes([rom.data[o] & 0x80 | age])))
        if kind == 2 and age is None:
            age = rom.jockey_record(i)[4] & 0x7F
        if kind == 2 and i == 0x1E:
            age += year
        code = face_code(kind, i, year, age or 0, rom.version)
        runs.append({"wram": wram, "patch": patch, "steps": "a:10 w200 a:10 w200", "shot": 320, "read": []})
        expect.append((kind, i, year, code))
    codes = {c for *_, c in expect}
    want = set(range(rom.face_count)) - ({104, 105} if rom.version == "program96" else set())
    assert codes == want, sorted(want ^ codes)
    lua = w2.COLLECT_LUA + LUA.replace("@DIALOG@", str(a["dialog"])).replace("@RET@", str(a["palette_ret"])) \
        .replace("@N@", str(FACE_BYTES)).replace("@PALETTE@", str(a["palette"]))
    boot = w2.new_game(rom.version) + w2.A * 60
    res = replay(rom.path, boot, end_frame(boot), runs, extra_lua=lua)
    ng = []
    for (kind, i, year, code), out in zip(expect, res):
        recs = w2.records(out[-2])
        if not recs:
            ng.append((kind, i, year, code, "no face"))
            continue
        raw = bytes.fromhex(recs[0][0])
        pal = (int.from_bytes(raw[:3], "big") - a["palette_base"]) // 32
        if raw[3:] != rom.face_bytes(code) or pal != face_palette_number(code):
            got = next((c for c in range(rom.face_count) if rom.face_bytes(c) == raw[3:]), None)
            ng.append((kind, i, year, code, f"got face {got} palette {pal}"))
    print(f"[faces] {len(runs) - len(ng)}/{len(runs)} runs ({len(codes)} face codes): pixels and palette = game"
          + (f" NG {ng[:6]}" if ng else ""))
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not ng else f"{len(ng)} problem(s)")
    raise SystemExit(1 if ng else 0)


if __name__ == "__main__":
    main()
