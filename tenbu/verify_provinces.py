#!/usr/bin/env python3
"""Check the 郡国 fields shown in the 郡国 window against rom.py.

Scenario 190, ruler row 1 (劉虞): on the map the view is scrolled one step left (◀), which puts the city of 代
(郡国 15) at the left edge, so the window that opens when it is clicked lies fully on the desktop; a savestate is
taken there. Each run copies fields of one 郡国 record (any scenario) over 代's WRAM record, clicks 代 and logs the
glyph codes of $00:A0CA. The window ($06:BEFA, read order 勢 人 兵 士 太 尉 金 糧 規) must show:

  勢 = name of faction +0 (FF: ——), 人 = +4 (LE16) x 100, 兵 = +6 (LE32), 士 = "+22/max" (max 80 when the high
  nibble of +27 is F, else 100), 太 = name of person +28 (LE16, FFFF: ——), 金 = +10 (LE16), 糧 = +12 (LE16),
  規 = +27 low nibble (0-4: 無 小 中 大 巨, table $06:A943)

The names come from the WRAM of the savestate (scenario 190), so 勢 / 太 are checked with that scenario's faction
and person tables. 尉 comes from a WRAM table ($7E:F920, 2 bytes per 郡国), not the record, and is not checked.
All 126 x 4 records, plus 5 runs with +27 low nibble = 0-4, 3 with +22 = 0 / 37 / 255
and 4 with +27 high nibble = 5 / A / E / F.

Usage: .venv/bin/python tenbu/verify_provinces.py [--rom ROM] [--scenario 0-3]
"""
import argparse
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import replay
import sequences as q
from rom import (
    DEFAULT_ROM,
    GLYPH_BASE,
    HALF_ORDER,
    PROVINCE_COUNT,
    PROVINCE_SIZE,
    PROVINCE_WRAM,
    SCENARIO_YEARS,
    Rom,
    le16,
)

TARGET = 15                       # 代
SIZES = 0x32943                   # $06:A943: 規模 strings, 4 bytes each (SJIS + FFFF)
FIELDS = [0, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 22, 27, 28, 29]   # copied record offsets
BOOT = (q.TO_SCENARIOS + " " + q.to_rulers(0) + " w200 " + q.card(1) + " " + q.START + " p:149:213 " + q.NUDGE
        + " b:10 w200")
CLICK = "w60 p:30:112 " + q.NUDGE + " b:10 w300"
SHOT = 400
WINDOW = re.compile(r"勢(.*)太(.*)人(\d+)尉(.*)兵(\d+)金(\d+)士(\d+)/(\d+)糧(\d+)屯港規(.)$")


def text(rom: Rom, codes: list[int]) -> str:
    """Glyph codes of $00:A0CA -> text (first code of each full-width glyph / half-width character)."""
    kanji, out = rom.kanji_list(), []
    for c in codes:
        t = c & 0x3FFF
        if 0x120 <= t < 0x120 + 2 * len(HALF_ORDER):
            if not (t - 0x120) % 2:
                out.append(HALF_ORDER[(t - 0x120) // 2])
        elif not c & 3:
            g = t // 4
            out.append(rom.sjis(kanji[g - GLYPH_BASE]) if GLYPH_BASE <= g < GLYPH_BASE + len(kanji) else f"<{g:x}>")
    return "".join(out)


def run(rom: Rom, k: int) -> int:
    records = [rom.province_raw(k, i) for i in range(PROVINCE_COUNT)]
    if k == 0:
        base = rom.province_raw(0, TARGET)
        records += [base[:27] + bytes([base[27] & 0xF0 | n]) + base[28:] for n in range(5)]
        records += [base[:22] + bytes([n]) + base[23:] for n in (0, 37, 255)]
        records += [base[:27] + bytes([h << 4 | base[27] & 15]) + base[28:] for h in (5, 10, 14, 15)]
    boot_r, save, steps, plua = q.prepare(BOOT, [CLICK] * len(records))
    rec = PROVINCE_WRAM + PROVINCE_SIZE * TARGET
    runs = [{"steps": st, "shot": SHOT, "read": [],
             "wram": [q.mail(i)] + [(rec + o, raw[o:o + 1]) for o in FIELDS]}
            for i, (st, raw) in enumerate(zip(steps, records))]
    lua = (plua + q.CODES_LUA.replace("CODES_FROM", "0")
           + "function EXTRA_RESET() POINTER_RESET(); CODES_START() end\n"
           + "function EXTRA_SHOT() return CODES_TAKE() end\n")
    results = replay.replay(rom.path, boot_r, save, runs, extra_lua=lua, nmi=q.MAP_HOOK)
    # an owned 郡国 also lists its armies (第一軍 ...), drawn row by row between the fields; some show a 徴発 label
    # next to 太 (its condition is not decoded): both are dropped before parsing
    parsed = [WINDOW.search(re.sub("第.軍|\u3000徴発\u3000", "", text(rom, q.codes(codes)))) for (codes,) in results]
    # the text the window shows for "none" (faction FF): taken from a record with faction FF
    none = next(m[1] for raw, m in zip(records, parsed) if m and raw[0] == 0xFF)
    bad = 0
    for i, (raw, m, (codes,)) in enumerate(zip(records, parsed, results)):
        if not m:
            bad += 1
            print(f"  NG {SCENARIO_YEARS[k]} 郡国 {i}: window not parsed: {text(rom, q.codes(codes))[-60:]}")
            continue
        f, person = raw[0], le16(raw, 28)
        want = {
            "勢": none if f == 0xFF else rom.sjis(rom.faction_raw(0, f)[:6]),
            "太": none if person == 0xFFFF else rom.person(0, person)["名前"],
            "人": le16(raw, 4) * 100, "兵": le16(raw, 6) | le16(raw, 8) << 16, "金": le16(raw, 10),
            "糧": le16(raw, 12), "士": raw[22], "/": 80 if raw[27] >> 4 == 15 else 100,
            "規": rom.sjis(rom.data[SIZES + 4 * (raw[27] & 15):][:2]),
        }
        got = {"勢": m[1], "太": m[2], "人": int(m[3]), "兵": int(m[5]), "金": int(m[6]), "士": int(m[7]),
               "/": int(m[8]), "糧": int(m[9]), "規": m[10]}
        diff = {key: (got[key], want[key]) for key in want if got[key] != want[key]}
        if diff:
            bad += 1
            print(f"  NG {SCENARIO_YEARS[k]} 郡国 {i}: {diff}")
    print(f"scenario {SCENARIO_YEARS[k]}: window equal for {len(records) - bad}/{len(records)} records")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證郡国欄位（郡国視窗）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--scenario", type=int, choices=(0, 1, 2, 3))
    args = ap.parse_args()
    t0 = time.time()
    if args.scenario is None:
        procs = [subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--scenario", str(k)])
                 for k in range(4)]
        errors = sum(p.wait() != 0 for p in procs)
        print(f"{time.time() - t0:.0f} s")
        print("ALL OK" if not errors else "mismatch(es)")
        raise SystemExit(1 if errors else 0)
    raise SystemExit(1 if run(Rom(args.rom), args.scenario) else 0)


if __name__ == "__main__":
    main()
