#!/usr/bin/env python3
"""Check the item table (movl file) against the game's 道具一覧 screen (needs Mesen 2, about a minute).

New game, field menu -> 情報 -> 人物選択 -> the hero -> 道具. The hero's 15 bag slots (WRAM $7E:F028, the copy
of sdata + 0x38) are filled with 15 item numbers per run before opening the menu; the screen lists them two per
row (rows 6, 8, ..., 20). Runs cover items 0-137 (the last run 123-137). Each row read back from VRAM (window
layer matched against the ROM font) must be the glyphs of the two item names (rom.Rom.items).

Usage: .venv/bin/python inindou/verify_items.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import end_frame, replay
from rom import DEFAULT_ROM, ITEM_COUNT, ITEM_SIZE, ITEMS, TEXT_BASE, Rom, text_codes
from scenes import BAG_WRAM, BOOT, SAVE, TILEMAP, TILEMAP_SIZE, WINDOW_CHR, WINDOW_CHR_SIZE, ScreenReader
from scenes import ITEMS as ITEM_STEPS

SLOTS = 15


def main() -> None:
    ap = argparse.ArgumentParser(description="以 Mesen 道具畫面驗證物品表")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    starts = list(range(0, ITEM_COUNT - SLOTS, SLOTS)) + [ITEM_COUNT - SLOTS]
    runs = [{"wram": [(BAG_WRAM, bytes(range(s, s + SLOTS)))], "steps": ITEM_STEPS,
             "shot": end_frame(ITEM_STEPS, 0),
             "read": [("vram", TILEMAP, TILEMAP_SIZE), ("vram", WINDOW_CHR, WINDOW_CHR_SIZE)]} for s in starts]
    results = replay(args.rom, BOOT, SAVE, runs)
    reader = ScreenReader(rom.data)

    def glyphs(n: int) -> list[int]:
        o = ITEMS + ITEM_SIZE * n + 1
        return [c - TEXT_BASE for c in text_codes(rom.data[o:o + 11]) if c - TEXT_BASE != 14]

    good, bad = set(), set()
    for s, (tm, chr_) in zip(starts, results):
        rows = reader.lines(tm, chr_)
        for k in range(0, SLOTS, 2):
            ids = [s + k] + ([s + k + 1] if k + 1 < SLOTS else [])
            want = [g for n in ids for g in glyphs(n)]
            (good if rows.get(6 + k, []) == want else bad).update(ids)
    good -= bad
    print(f"[items] {len(good)}/{ITEM_COUNT} item names match the 道具一覧 screen"
          + (f" (NG {sorted(bad)[:20]})" if bad else ""))
    print("ALL OK" if not bad and len(good) == ITEM_COUNT else "problem(s)")
    raise SystemExit(0 if not bad and len(good) == ITEM_COUNT else 1)


if __name__ == "__main__":
    main()
