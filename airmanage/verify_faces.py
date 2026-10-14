#!/usr/bin/env python3
"""Check the 33 portraits and their palettes against the game in Mesen.

New game in scenario 2 (home London, COM players in Vancouver, Tokyo and Paris), main screen saved. The game
draws the player's aide from the face descriptor at WRAM $7146 (kind LE16, image, palette) when A opens
the command menu. For every portrait the descriptor is replaced (kind 0 MANAGER, 1 PERSON, 2 MAKER: the game's
loader ALNMAIN $25C3 handles all three) with the palette rom.py pairs with it, and the 960 bytes the game
writes to VRAM $3700 and the 16 colours of CGRAM palette 7 are compared with rom.py.

The pairing itself is checked on the descriptors the game's set-up wrote for the 4 players (OPENING $A6EE:
aide at $7146 + 4p, $A7A7: 3 negotiation partners at $7156 + 12p + 4k).
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import vm
from replay import replay
from rom import DEFAULT_ROM, FACE_BYTES, Rom, le16

FACE_VRAM, FACE_CGRAM = 0x3700, 0xE0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="first portrait of each kind only")
    args = ap.parse_args()
    r = Rom(args.rom)
    t = time.time()
    faces = r.faces()
    if args.quick:
        faces = [f for f in faces if f["image"] == 0]
    a = vm.addresses(r.rev)
    reads = [("vram", FACE_VRAM, FACE_BYTES), ("cgram", FACE_CGRAM, 32), ("wram", a["face_desc"], 64),
             ("wram", a["player_rec"], 256)]
    runs = [{"steps": "a:10", "shot": 120, "read": reads}]  # untouched: the game's own descriptors
    runs += [{"wram": [(a["face_desc"], bytes([f["kind"], 0, f["image"], f["palette"]]))], "steps": "a:10", "shot": 120,
              "read": reads} for f in faces]
    res = replay(r.path, vm.boot(1), vm.MAIN_FRAME, runs, extra_lua=vm.boot_lua(r.rev))
    bad = 0
    # the game's own pairing
    desc, players = res[0][2], res[0][3]
    pairs = []
    for p in range(4):
        home = le16(players, 64 * p + 2)
        pairs.append((home, desc[4 * p:4 * p + 4]))
        pairs += [(home, desc[16 + 12 * p + 4 * k:16 + 12 * p + 4 * k + 4]) for k in range(3)]
    pbad = 0
    for home, d in pairs:
        kind, img, pal = le16(d, 0), d[2], d[3]
        if pal != r.default_palette(kind, img):
            print(f"  home {home}: descriptor kind {kind} image {img} palette {pal}, rom.py {r.default_palette(kind, img)}")
            pbad += 1
    print(f"game's descriptors (4 players x aide + 3 partners): {len(pairs) - pbad}/{len(pairs)} palettes OK, "
          f"e.g. {[(h, d.hex()) for h, d in pairs[:4]]}")
    bad += pbad
    ok = 0
    for f, run in zip(faces, res[1:]):
        vram, cg = run[0], run[1]
        want_cg = bytes(b for c in r.face_palette(f["palette"]) for b in c.to_bytes(2, "little"))
        if vram == r.face_raw(f["kind"], f["image"]) and cg[2:] == want_cg[2:]:
            ok += 1
        else:
            diff = sum(vram[i:i + 32] != r.face_raw(f["kind"], f["image"])[i:i + 32] for i in range(0, FACE_BYTES, 32))
            print(f"  {f['file']} {f['image']}: {diff} tiles differ, palette {'OK' if cg[2:] == want_cg[2:] else 'NG'}")
    print(f"portraits: {ok}/{len(faces)} OK (VRAM ${FACE_VRAM:04X} 960 bytes, CGRAM palette 7 colours 1-15)")
    bad += len(faces) - ok
    print(f"{'OK' if not bad else f'{bad} mismatches'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
