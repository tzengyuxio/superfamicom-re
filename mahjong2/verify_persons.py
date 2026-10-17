#!/usr/bin/env python3
"""Check the opponent tables (parlors, name graphics, card faces and palettes, playing parameters) in Mesen.

1. Parlors ($01:D41C): a savestate on the 雀荘 selection (tools/sequences.py TO_PARLORS) is replayed for each of the
   7 parlors (top row: right x 0-3; bottom row: down, right x 0-2), then a, and the card list is scrolled down 0, 3 and
   6 times. The list $00:AF13 builds at $0423 must hold exactly rom.parlor_persons(k). Every 5x5 block of consecutive
   tiles in the BG tilemap ($0800) is a card face: its VRAM tiles must equal rom.face_tiles(p, 0) of some opponent p,
   the CGRAM row of its palette must be $02:8000 + 32 x $01:CCB1[p], and the 8x2 block below it (two columns to the
   left) must be rom.name_tiles(p) (top row then bottom row), palette 3. All 23 parlor opponents must be seen.
2. Parameters ($01:DA92 + 12p): a savestate before $01:C999 (the start of a game) is replayed 9 times; the hook puts
   three opponents into slots 1-3 ($199E), and the 30 values per seat the routine writes below $13D9 + 0x80 must be
   rom.params of the slot's person (22 nibbles, high first, and 8 flags as 00/FF), seat order from $1998. Slot 0 is the
   player (entry 0).

Usage: .venv/bin/python mahjong2/verify_persons.py [--rom ROM]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import sequences as sq
from replay import end_frame, presses, replay
from rom import DEFAULT_ROM, FACE_PAL, PALETTES, PARLOR_COUNT, PARLOR_PERSONS, PERSONS, Rom

CARD_TILEMAP = 0x0800
NAVIGATION = ["", "right:6 w30", "right:6 w30 right:6 w30", "right:6 w30 right:6 w30 right:6 w30", "down:6 w30",
              "down:6 w30 right:6 w30", "down:6 w30 right:6 w30 right:6 w30"]
SCROLLS = (0, 3, 6)
NAME_PAL = 3


def cards(tilemap: bytes, vram: bytes, cgram: bytes, rom: Rom) -> list[tuple]:
    """[(person or None, palette ok, name ok)] of the card faces in the tilemap."""
    def word(r: int, c: int) -> int:
        return tilemap[2 * (r * 32 + c)] | tilemap[2 * (r * 32 + c) + 1] << 8

    def tiles(r: int, c: int, w: int, h: int) -> tuple[bytes, set[int]]:
        ws = [word(r + y, c + x) for y in range(h) for x in range(w)]
        return b"".join(vram[sq.BG_CHR + 32 * (v & 0x3FF):sq.BG_CHR + 32 * (v & 0x3FF) + 32] for v in ws), \
            {v >> 10 & 7 for v in ws}

    faces = {rom.face_tiles(p, 0): p for p in PERSONS}
    out = []
    for r in range(32 - 6):
        for c in range(2, 32 - 5):
            t0 = word(r, c) & 0x3FF
            if t0 < 0x100 or any(word(r + y, c + x) & 0x3FF != t0 + 5 * y + x for y in range(5) for x in range(5)):
                continue
            data, pal = tiles(r, c, 5, 5)
            p = faces.get(data)
            if p is None:
                out.append((None, False, False))
                continue
            k = rom.data[FACE_PAL + p - 1]
            pal_ok = len(pal) == 1 and cgram[32 * min(pal):32 * min(pal) + 32] == rom.data[PALETTES + 32 * k:PALETTES + 32 * k + 32]
            name, npal = tiles(r + 5, c - 2, 8, 2)
            out.append((p, pal_ok, name == rom.name_tiles(p) and npal == {NAME_PAL}))
    return out


def expand_params(rom: Rom, slots: list[int], seat_slot: bytes) -> dict[int, int]:
    """{offset from $13D9: value} as $01:C999 writes it, for the persons in slots."""
    out, x = {}, 0x80
    for y in range(3, -1, -1):
        pr = rom.params(slots[seat_slot[y]])["raw"]
        x -= 2
        b = pr[11]
        for _ in range(8):
            x -= 1
            out[x] = 0xFF if b & 1 else 0
            b >>= 1
        for i in range(10, -1, -1):
            x -= 1
            out[x] = pr[i] & 15
            x -= 1
            out[x] = pr[i] >> 4
    return out


def check_parlors(rom: Rom) -> int:
    reads = [("wram", 0x0423, 24), ("vram", 0, 0x10000), ("cgram", 0, 512)]
    runs, what = [], []
    for k in range(PARLOR_COUNT):
        for s in SCROLLS:
            steps = " ".join(filter(None, [NAVIGATION[k], "a:10 w300"] + ["down:6 w40"] * s))
            runs.append({"steps": steps, "shot": end_frame(steps, 0) + 40, "read": reads})
            what.append((k, s))
    res = replay(rom.path, sq.TO_PARLORS, end_frame(sq.TO_PARLORS), runs, timeout=900)
    bad_list, bad_card, seen = [], [], {}
    for (k, s), (lst, vram, cgram) in zip(what, res):
        got = sorted(lst[:lst.index(0)] if 0 in lst else lst)
        if s == 0:
            ok = got == rom.parlor_persons(k)
            print(f"parlor {k}: list {list(lst[:lst.index(0)])} " + ("OK" if ok else f"NG (want {rom.parlor_persons(k)})"))
            if not ok:
                bad_list.append(k)
        for p, pal_ok, name_ok in cards(vram[CARD_TILEMAP:CARD_TILEMAP + 0x800], vram, cgram, rom):
            if p is None or p not in got or not (pal_ok and name_ok):
                bad_card.append((k, s, p, pal_ok, name_ok))
            else:
                seen.setdefault(p, set()).add(k)
    want_seen = {p: {k for k in range(PARLOR_COUNT) if p in rom.parlor_persons(k)} for p in PARLOR_PERSONS}
    n_seen = sum(seen.get(p) == want_seen[p] for p in PARLOR_PERSONS)
    print(f"[parlors] {PARLOR_COUNT - len(bad_list)}/{PARLOR_COUNT}: $0423 = opponents with $01:D41C = 0 or the parlor")
    print(f"[cards] {n_seen}/{len(PARLOR_PERSONS)} opponents seen in exactly their parlors; face 0, name graphic and palette"
          + (f" NG {bad_card[:5]}" if bad_card else ""))
    return len(bad_list) + len(bad_card) + (n_seen != len(PARLOR_PERSONS))


def check_params(rom: Rom) -> int:
    pre = next(p for p in presses(sq.TO_GAME, 10) if p[0] > sq.PARAMS_SAVE)[0] - sq.PARAMS_SAVE
    trios = [[(3 * i + j) % len(PERSONS) + 1 for j in range(3)] for i in range((len(PERSONS) + 2) // 3)]
    runs = []
    for t in trios:
        pw = bytearray(16)
        pw[8:12] = (1, *t)
        runs.append({"steps": f"w{pre} a:10", "shot": pre + 250, "wram": [(sq.PARAM & 0xFFFF, bytes(pw))],
                     "read": [("wram", sq.SEAT_SLOT, 10), ("wram", sq.PARAM_BUF, 0x80)]})
    res = replay(rom.path, sq.TO_GAME, sq.PARAMS_SAVE, runs, extra_lua=sq.HOOK_LUA, timeout=600)
    bad_par, checked = [], set()
    for t, (slots, buf) in zip(trios, res):
        persons = list(slots[6:10])
        if persons[1:] != t:
            bad_par.append(("slots", t, persons))
            continue
        want = expand_params(rom, persons, slots[:4])
        if any(buf[o] != v for o, v in want.items()):
            bad_par.append(("values", t))
        else:
            checked.update(persons)
    n_par = len(checked & set(PERSONS))
    print(f"[params] {n_par}/{len(PERSONS)} opponents (+ the player, entry 0: {'OK' if 0 in checked else 'NG'}): "
          "$13D9 = $01:DA92 + 12p expanded" + (f" NG {bad_par[:5]}" if bad_par else ""))
    return len(bad_par) + (n_par != len(PERSONS)) + (0 not in checked)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證對手的雀荘、名字圖、頭像卡片與打牌參數（Mesen）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--part", choices=("parlors", "params"), help="run one part (each part opens Mesen once)")
    args = ap.parse_args()
    t0 = time.time()
    if args.part:
        rom = Rom(args.rom)
        errors = check_parlors(rom) if args.part == "parlors" else check_params(rom)
        sys.stdout.flush()
        raise SystemExit(min(errors, 100))
    errors = 0
    for part in ("parlors", "params"):  # a second Mesen in one process crashes: one subprocess per part
        errors += subprocess.run([sys.executable, __file__, "--rom", args.rom, "--part", part], check=False).returncode
    print(("ALL OK" if not errors else f"{errors} problem(s)") + f" ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
