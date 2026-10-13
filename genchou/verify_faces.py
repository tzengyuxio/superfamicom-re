#!/usr/bin/env python3
"""Check rom.Rom.face_tiles / face_palette_number against the game (needs Mesen 2, about 1 minute).

Two scenes of scenario 1 (savestate replay, tools/replay.py) show a face drawn by the game's own code:
  A: 人事 → 政治顧問 → オノン河流域 → カサル: the card "カサル殿を…の顧問にしますか" draws the face of the family
     record カサル ($7E:4C94, face code at +24) with the person face routine $C4:5EDB.
  B: 人事 → 后妃 → ボルテ: the night scene draws the face of woman 0 ($7E:4F38, face code at +19) with the
     woman face routine $C4:5F63 (portraits: LZ entry 38 + 57 + code).
For every face code the record's face field is overwritten in WRAM before the last press; afterwards the 960
bytes of the face's VRAM slot (A: byte 0xBB80, B: 0xB7C0) must equal Rom.face_tiles(code, woman), the BG
tilemap of the face (A: VRAM 0xEC44, B: 0x9CF2, 6 rows x 5) must use palette Rom.face_palette_number(code), and
that CGRAM palette must equal the ROM copy at FACE_PALETTES. Codes: portraits 0-56 and every composed code of
a person or the family in scene A; woman portraits 0-39 and every composed code of a woman in scene B.

Usage: .venv/bin/python genchou/verify_faces.py [--rom ROM]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import presses, replay
from rom import (
    B_WRAM,
    DEFAULT_ROM,
    FACE_BYTES,
    FACE_PALETTES,
    PORTRAIT_COUNT,
    SCENARIO_COUNT,
    WOMAN_PORTRAIT,
    Rom,
)

# scenario 1, one player, モンゴル族; first turn: 人事 (down x2, a), then
TO_JINJI = ("w2100 start:30 w100 start:4 w300 a:10 w200 a:10 w200 a:10 w200 a:10 w200 a:10 w200 a:10 w200 "
            "a:10 w200 a:10 w200 a:10 w300 a:10 w300 a:10 w300 a:10 w300 down:10 w30 down:10 w30 a:10 w200")
SCENES = {
    # 政治顧問 (down), yes, オノン河流域, list -> card on the last press
    "A": {"boot": TO_JINJI + " down:10 w40 a:10 w200 a:10 w200 a:10 w200 a:10 w200 a:10 w200",
          "record": 0x4C94 + 24, "vram": 0xBB80, "tilemap": 0xEC44, "woman": False},
    # 后妃 (down x2, right), yes, ボルテ, description -> night scene on the last press
    "B": {"boot": TO_JINJI + " down:10 w30 down:10 w30 right:10 w30 a:10 w200 a:10 w200 a:10 w200 a:10 w200",
          "record": B_WRAM + 19, "vram": 0xB7C0, "tilemap": 0x9CF2, "woman": True},
}
SHOT = 200


def save_frame(steps: str) -> int:
    """First frame after the last press of steps and its wait, as replay counts them."""
    last = presses(steps, 10)[-1]
    return last[0] + last[2] + 20 + int(steps.split()[-1][1:])


def check(rom: Rom, path: str, scene: str, codes: list[int]) -> list[str]:
    sc = SCENES[scene]
    runs = [{"wram": [(sc["record"], c.to_bytes(2, "little"))], "steps": "a:10", "shot": SHOT,
             "read": [("vram", sc["vram"], FACE_BYTES), ("vram", sc["tilemap"], 6 * 64), ("cgram", 0, 256)]}
            for c in codes]
    bad = []
    for code, (tiles, tmap, cgram) in zip(codes, replay(path, sc["boot"], save_frame(sc["boot"]), runs)):
        n = rom.face_palette_number(code, sc["woman"])
        pals = {tmap[64 * r + 2 * c + 1] >> 2 & 7 for r in range(6) for c in range(5)}
        ok = (tiles == rom.face_tiles(code, sc["woman"]) and pals == {n}
              and cgram[32 * n:32 * n + 32] == rom.data[FACE_PALETTES[n]:FACE_PALETTES[n] + 32])
        if not ok:
            bad.append(f"{code:#06x}")
    return bad


def run_scene(rom: Rom, path: str, scene: str) -> int:
    men, women = set(), set()
    for s in range(SCENARIO_COUNT):
        men |= {p["face"] for p in rom.persons(s)}
        women |= {w["face"] for w in rom.women(s)}
    men |= {p["face"] for p in rom.family()}
    if scene == "A":
        groups = [("man portraits", list(range(WOMAN_PORTRAIT))),
                  ("man composed faces", sorted(c for c in men if c & 0x8000))]
    else:
        groups = [("woman portraits", list(range(PORTRAIT_COUNT - WOMAN_PORTRAIT))),
                  ("woman composed faces", sorted(c for c in women if c & 0x8000))]
    bad = set(check(rom, path, scene, [c for _, codes in groups for c in codes]))
    errors = 0
    for label, codes in groups:
        ng = [f"{c:#06x}" for c in codes if f"{c:#06x}" in bad]
        errors += len(ng)
        print(f"[{label}] scene {scene}: {len(codes) - len(ng)}/{len(codes)} codes: VRAM tiles = face_tiles, "
              f"tilemap palette = face_palette_number, CGRAM = ROM palette" + (f"  NG {ng}" if ng else ""),
              flush=True)
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證頭像解碼（專屬頭像與組合臉，男女）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scene", choices=list(SCENES), help=argparse.SUPPRESS)  # one Mesen per process
    args = ap.parse_args()
    t0 = time.time()
    if args.scene:
        raise SystemExit(1 if run_scene(Rom(args.rom), args.rom, args.scene) else 0)
    errors = 0
    for scene in SCENES:
        cmd = [sys.executable, __file__, "--rom", args.rom, "--scene", scene]
        errors += subprocess.run(cmd, check=False).returncode != 0
    print(f"{'ALL OK' if not errors else 'PROBLEMS'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
