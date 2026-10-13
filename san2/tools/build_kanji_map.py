#!/usr/bin/env python3
"""Build data/kanji_ext.json: the game's 2-byte kanji codes -> kanji, from external person names.

The ROM stores names as private 2-byte codes (not Shift-JIS). Pairing the 352 name records
with the PC 三國志II person table (kaodata-re PERSONS_TABLE/san2_persons.csv) gives the kanji
for every code used in a name. The two lists are aligned on name length + already-known codes
(the SFC order differs from the PC table around id 179). Errors in the PC table are fixed
by hand below.

Usage: .venv/bin/python san2/tools/build_kanji_map.py --pc <kaodata-re>/PERSONS_TABLE/san2_persons.csv
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rom import DEFAULT_ROM, Rom

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kanji_ext.json")
# Codes the alignment cannot get from the PC table, fixed by the ROM reading:
# PC id 157 repeats 樂進 where the SFC has ｳｷﾝ 于禁, and ｼﾞｭﾝｳｹｲ 淳于瓊 falls in a gap of the alignment
# Shared codes where the PC table disagrees with itself: 81D7 is used by 孫桓・朱桓・ｶﾝｶｲ (桓階),
# 82D2 by 趙範・呂範
# The PC table simplifies some names; the ROM glyphs (font at 0x80000) show 阿會喃, 蔡瑁, 董荼奴, 嚴畯, 劉璝, 張顗
FIXES = {0x832D: "于", 0x81F5: "禁", 0x8250: "淳", 0x8354: "瓊", 0x81D7: "桓", 0x82D2: "範",
         0x8332: "喃", 0x8350: "瑁", 0x8363: "荼", 0x8387: "畯", 0x8396: "璝", 0x838A: "顗"}
# The PC table writes old forms; the ROM glyphs (and the FC version) use the Japanese new forms
SHINJITAI = dict(zip("儉勳吳嚴國圖廣德惠應懷會榮樂橫權步溫滿澤濟熙當禪禮繡續肅蔣覽觀觸豐鐵關雙霸靈顏黃默齡",
                     "倹勲呉厳国図広徳恵応懐会栄楽横権歩温満沢済煕当禅礼繍続粛蒋覧観触豊鉄関双覇霊顔黄黙齢"))


def align(sfc: list[list[int]], pc: list[str], known: dict[int, str]) -> list[tuple[int, int]]:
    """Global alignment (Needleman-Wunsch) of SFC code lists with PC names."""
    def score(i: int, j: int) -> int:
        a, b = sfc[i], pc[j]
        if len(a) != len(b):
            return -3
        return 1 + sum((3 if known[c] == ch else -20) for c, ch in zip(a, b) if c in known)

    n, m = len(sfc), len(pc)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    bt = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        for j in range(m + 1):
            if i == j == 0:
                continue
            best = (-10**9, "")
            if i and j:
                best = max(best, (dp[i - 1][j - 1] + score(i - 1, j - 1), "d"))
            if i:
                best = max(best, (dp[i - 1][j] - 2, "u"))
            if j:
                best = max(best, (dp[i][j - 1] - 2, "l"))
            dp[i][j], bt[i][j] = best
    i, j, pairs = n, m, []
    while i or j:
        step = bt[i][j]
        if step == "d":
            pairs.append((i - 1, j - 1))
        i, j = i - (step in "du"), j - (step in "dl")
    return pairs[::-1]


def main() -> None:
    ap = argparse.ArgumentParser(description="從 PC 版人物表推出漢字碼對照")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--pc", required=True, help="kaodata-re 的 PERSONS_TABLE/san2_persons.csv")
    args = ap.parse_args()
    with open(args.pc, encoding="utf-8-sig") as f:
        pc = [r["姓名"] for r in csv.DictReader(f)]
    sfc = [p["kanji_codes"] for p in Rom(args.rom).persons()]
    # seed: same order up to the first length mismatch (the SFC order drifts from the PC table later)
    n = next(i for i in range(len(sfc)) if len(sfc[i]) != len(pc[i]))
    pairs = [(i, i) for i in range(n)]
    for _ in range(4):  # re-align with what the previous pass learned (majority vote per code)
        votes: dict[int, Counter] = {}
        for i, j in pairs:
            if len(sfc[i]) == len(pc[j]):
                for c, ch in zip(sfc[i], pc[j]):
                    votes.setdefault(c, Counter())[ch] += 1
        known = {c: v.most_common(1)[0][0] for c, v in votes.items()}
        pairs = align(sfc, pc, known)
    known.update(FIXES)
    known = {c: SHINJITAI.get(ch, ch) for c, ch in known.items()}
    missing = sorted({c for codes in sfc for c in codes} - set(known))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({f"{c:04X}": known[c] for c in sorted(known)}, f, ensure_ascii=False, indent=0)
        f.write("\n")
    print(f"{len(known)} codes → {OUT}; unresolved: {' '.join(f'{c:04X}' for c in missing) or '-'}")


if __name__ == "__main__":
    main()
