#!/usr/bin/env python3
"""Check the 68 faces (rom.Rom.face_tiles / face_palette) against the game's screen (needs Mesen 2, ~1 minute).

1. House select screen of scenario 1 (cursor on ブランシェ). The lords of the 4 selectable houses come from a
   4-byte list per scenario in the p-code (ROM 0x1C706, loaded to WRAM $65CC with its overlay); for every face
   0-67 the second entry ($65CD, ライル) is set to n and the cursor moved down, so the game draws face n itself.
2. The advisor screen (5 presses later) draws the 4 advisor faces without any patch.

On each screen the BG1 tilemap is searched for 5x6 blocks of consecutive tile numbers (row-major, one
palette); each block is drawn from the VRAM tiles and the CGRAM palette and compared pixel by pixel with
rom.Rom.face_rgb. Unpatched, the house screen must show face 4 (エラン, lord of ブランシェ).

Usage: .venv/bin/python royal/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import end_frame, replay
from rom import DEFAULT_ROM, FACE_COUNT, FACE_H, FACE_W, Rom, bgr555_rgb, decode_tile, le16

BOOT = "w1500 start w200 start w200 a:10 w200 a:10 w200 a:10 w400"   # title -> scenario 1 -> 1 player -> houses
LORD_LIST = 0x65CD                       # WRAM: second selectable lord of scenario 1
CHR, BG1_MAP = 0x4000, 0xD000            # VRAM bytes: BG1/BG2 chr base, BG1 tilemap (64x32: two 32x32 screens)
ADVISORS = list(range(64, 68))


def faces_on_screen(rom: Rom, vram_chr: bytes, tilemap: bytes, cgram: bytes) -> list[tuple[int, bool]]:
    """[(face, pixels equal)] for every 5x6 block of consecutive tiles on BG1 that holds a face's tiles."""
    def entry(x: int, y: int) -> int:
        a = (x // 32) * 0x800 + (y * 32 + x % 32) * 2
        return le16(tilemap, a)

    found = []
    for y in range(32 - FACE_H + 1):
        for x in range(64 - FACE_W + 1):
            e0 = entry(x, y)
            if any(entry(x + k % FACE_W, y + k // FACE_W) != e0 + k for k in range(FACE_W * FACE_H)):
                continue
            t0 = (e0 & 0x3FF) * 32
            tiles = vram_chr[t0:t0 + 960]
            face = next((f for f in range(FACE_COUNT) if rom.face_tiles(f) == tiles), None)
            if face is None:
                continue
            pal = [bgr555_rgb(le16(cgram, 32 * (e0 >> 10 & 7) + 2 * i)) for i in range(16)]
            px = [0] * (FACE_W * FACE_H * 64)
            for t in range(FACE_W * FACE_H):
                for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                    px[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
            found.append((face, [pal[v] for v in px] == rom.face_rgb(face)))
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 68 張頭像")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    reads = [("vram", CHR, 0x4000), ("vram", BG1_MAP, 0x1000), ("cgram", 0, 512)]
    down, adv = "down:10 w150", "a:10 w200 " * 5
    runs = [{"steps": "w150", "shot": 150, "read": reads}]
    runs += [{"wram": [(LORD_LIST, bytes([n]))], "steps": down, "shot": end_frame(down, 0), "read": reads}
             for n in range(FACE_COUNT)]
    runs.append({"steps": adv, "shot": end_frame(adv, 0), "read": reads})
    got = replay(args.rom, BOOT, end_frame(BOOT), runs)
    shown = [faces_on_screen(rom, *g) for g in got]

    natural = shown[0]
    print(f"[house screen] unpatched shows {natural} (want [(4, True)])")
    ok = [n for n in range(FACE_COUNT) if (n, True) in shown[1 + n] and all(f == n for f, _ in shown[1 + n])]
    bad = sorted(set(range(FACE_COUNT)) - set(ok))
    print(f"[faces] {len(ok)}/{FACE_COUNT}: face n drawn by the game equals the ROM decoding pixel for pixel"
          + (f" (NG {bad})" if bad else ""))
    adv_ok = sorted(f for f, eq in shown[-1] if eq)
    print(f"[advisors] advisor screen shows {sorted(f for f, _ in shown[-1])}, equal {adv_ok} (want {ADVISORS})")
    errors = (natural != [(4, True)]) + len(bad) + (adv_ok != ADVISORS)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
