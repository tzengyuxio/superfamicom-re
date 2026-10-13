#!/usr/bin/env python3
"""Check the 250 persons (rom.Rom.persons, person_states 名声, face_tiles) against the game (needs Mesen 2,
about 4 minutes).

New game, America: the side selection screen shows the commander ジョージ・ワシントン (person 238): $C8:375D..
loads the person id as an immediate (LDA #$00EE, ten sites, #$0052 = トーマス・ゲージ for Britain). A savestate is
taken just before the screen is built; for every person k the ten immediates are patched to k and the state
replayed. The game's vprintf ($C1:430F) is hooked: "%s %s" must get the pointers of master +2 / +14 of record k,
統率力 戦術力 指導力 must equal master +26..+28 and 名声 person state +4; the face the game puts at VRAM 0x9860
(30 tiles in a row) must equal rom.Rom.face_tiles(master +31), and CGRAM palette 2 the face palette.

Usage: .venv/bin/python dokuritsu/verify_persons.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import DEFAULT_ROM, FACE_BYTES, FACE_PALETTE, PERSON_COUNT, PERSON_SIZE, PERSONS, Rom, le16

BOOT = "w9800 start:10 w200 a:10 w200 a:10 w200 a:10 w200 a:10 w300"   # title -> 新しく始める -> America
SAVE_AT = 10745
SHOT = 200
SITE_RANGE = (0x83700, 0x83C00)
FACE_VRAM = 0x9860
FMTS = [0xC8AE11, 0xC8AE1B, 0xC8AE26, 0xC8AE31, 0xC8AE3C]   # "%s %s", 統率力, 戦術力, 指導力, 名声
EXTRA = """
local pf = {}
local fmts = {FMTS}
function EXTRA_RESET() pf = {} end
function EXTRA_SHOT()
  local out = {}
  for _, f in ipairs(fmts) do out[#out + 1] = pf[f] or "ffffffffffffffff" end
  return table.concat(out)
end
emu.addMemoryCallback(function()
  local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
  local sp = emu.getState()["cpu.sp"]
  local fmt = rd(sp + 4) + rd(sp + 5) * 256 + rd(sp + 6) * 65536
  local va = rd(sp + 8) + rd(sp + 9) * 256 + rd(sp + 10) * 65536
  local s = {}
  for i = 0, 7 do s[#s + 1] = string.format("%02x", rd(va + i)) end
  pf[fmt] = table.concat(s)
end, emu.callbackType.exec, 0xC1430F, 0xC1430F)
""".replace("{FMTS}", "{" + ",".join(str(f) for f in FMTS) + "}")


def sites(rom: Rom) -> list[int]:
    out, p = [], rom.data.find(b"\xa9\xee\x00", *SITE_RANGE)
    while p >= 0:
        out.append(p + 1)
        p = rom.data.find(b"\xa9\xee\x00", p + 1, SITE_RANGE[1])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 250 名人物")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 10th person")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    st = sites(rom)
    assert len(st) == 10, st
    ids = list(range(0, PERSON_COUNT, 10 if args.quick else 1))
    read = [("vram", FACE_VRAM, FACE_BYTES), ("cgram", 0x40, 32)]
    runs = [{"patch": [(s, bytes([k])) for s in st], "shot": SHOT, "read": read} for k in ids]
    shots = replay(args.rom, BOOT, SAVE_AT, runs, extra_lua=EXTRA)
    persons, states = rom.persons(), rom.person_states()
    pal = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    bad = {"name": [], "stats": [], "名声": [], "face": [], "palette": []}
    for k, (vram, cg, pf) in zip(ids, shots):
        p = persons[k]
        a = [pf[8 * i:8 * i + 8] for i in range(len(FMTS))]
        ptrs = [int.from_bytes(a[0][j:j + 3], "little") & 0x3FFFFF for j in (0, 4)]
        if ptrs != [PERSONS + PERSON_SIZE * k + 2, PERSONS + PERSON_SIZE * k + 14]:
            bad["name"].append(k)
        if [le16(x, 0) for x in a[1:4]] != [p["統率力"], p["戦術力"], p["指導力"]]:
            bad["stats"].append(k)
        if le16(a[4], 0) != states[k]["名声"]:
            bad["名声"].append(k)
        if vram != rom.face_tiles(p["face"]):
            bad["face"].append(k)
        if cg != pal:
            bad["palette"].append(k)
    n = len(ids)
    print(f"[persons] {n} persons shown on the side selection screen by patching person 238 -> k")
    for key, label in [("name", "名前 pointers (master +2 / +14)"), ("stats", "統率力 戦術力 指導力 (master +26..+28)"),
                       ("名声", "名声 (person state +4)"), ("face", "face tiles (master +31 -> face_tiles)"),
                       ("palette", f"CGRAM palette 2 = 0x{FACE_PALETTE:X}")]:
        print(f"  {label}: {n - len(bad[key])}/{n}" + (f" NG {bad[key][:10]}" if bad[key] else ""))
    errors = sum(len(v) for v in bad.values())
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
