#!/usr/bin/env python3
"""Check the daimyo, province and text decoding against the game's province screen (needs Mesen 2, about 2
minutes).

Scenario 2, one player (織田信長), first turn: その他 → 情報 → 国 → "どの国をご覧になりますか" with the cursor on
尾張 (province 24, daimyo slot 24); a shows the province screen: province name, daimyo name, the 12 province
values, 年齢 and the 5 daimyo values (half-width digits) and the daimyo's face (30 sprites, OBJ tiles 0x10-0x2D).
Before the press every run overwrites, in WRAM, daimyo slot 24 (record $2F7E, surname $3193, given name $3306)
and province 24 (record $340F, name $39A7), then reads the BG3 text back by exact comparison with the ROM fonts
(scenes.Screen) and the face tiles from VRAM 0xC200:
  * every daimyo slot and every province of the 4 scenarios (ROM records): names (glyph numbers = rom.codes),
    the 12 values and 年齢 + 5 values, face tiles = LZ stream 120 + person id;
  * 2 runs with made-up values (every field different) pin down which field is shown where;
  * the text runs put 9 consecutive glyph codes into the names (province 4 + surname 3 + given name 2), so every
    one of the 636 glyphs is drawn once (codes with low byte 00 use the 0x9140 escape);
  * person ids 68-72 (the women's portraits) in the face byte.

Usage: .venv/bin/python zenkoku/verify_persons.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from replay import replay
from rom import (
    CODE_BASE,
    DAIMYO_SIZE,
    DAIMYO_STATS,
    DAIMYO_WRAM,
    DEFAULT_ROM,
    FACE_BYTES,
    FACE_PALETTE,
    GIVEN_SIZE,
    GIVEN_WRAM,
    GLYPH_COUNT,
    PORTRAIT_COUNT,
    PROVINCE_FIELDS,
    PROVINCE_NAME_SIZE,
    PROVINCE_NAMES_WRAM,
    PROVINCE_SIZE,
    PROVINCES_WRAM,
    SCENARIO_COUNT,
    SURNAME_SIZE,
    SURNAMES_WRAM,
    ZERO_ESCAPE,
    Rom,
)
from scenes import TO_INFO, Screen, save_frame

SLOT = 24                       # 織田信長 / 尾張 in scenario 2
STEPS, SHOT = "a:10 w150", 180
FACE_VRAM = 0xC200              # OBJ tile 0x10
FACE_CGRAM = 2 * (128 + 16 * 5)  # OBJ palette 5
PROVINCE_NAME_AT, DAIMYO_NAME_AT = (9, 6), (12, 9)
# right end (tile x) and row of each number: province fields by name, then 年齢 and the daimyo values
NUMBERS = {"Soldiers": (8, 12), "Gold": (15, 12), "Town": (22, 12),
           "Soldier_Loyalty": (8, 14), "Rice": (15, 14), "Flood": (22, 14),
           "Arms": (8, 16), "Loyalty": (15, 16), "Kokudaka": (22, 16),
           "Training": (8, 18), "Wealth": (15, 18), "Debt": (22, 18),
           "age": (29, 8), "Health": (29, 10), "Ambition": (29, 12), "Luck": (29, 14), "Charm": (29, 16),
           "IQ": (29, 18)}
WIDTH = 3
SHOWN_FIELDS = [k for k, _ in PROVINCE_FIELDS if k in NUMBERS]


def encode(glyphs: list[int], size: int) -> bytes:
    """Glyph numbers -> NUL-padded text bytes of the field (with the 00 escape)."""
    out = bytearray()
    for g in glyphs:
        c = CODE_BASE + g
        if c & 0xFF == 0:
            c = ZERO_ESCAPE + ((c >> 8) - 0x82)
        out += c.to_bytes(2, "big")
    assert len(out) < size
    return bytes(out) + bytes(size - len(out))


def record_bytes(values: dict, fields: list[str]) -> bytes:
    return b"".join(values[k].to_bytes(2, "little") for k in fields)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證大名、國資料與文字編碼（情報畫面）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    d_at = DAIMYO_WRAM + DAIMYO_SIZE * SLOT
    s_at, g_at = SURNAMES_WRAM + SURNAME_SIZE * SLOT, GIVEN_WRAM + GIVEN_SIZE * SLOT
    p_at, n_at = PROVINCES_WRAM + PROVINCE_SIZE * SLOT, PROVINCE_NAMES_WRAM + PROVINCE_NAME_SIZE * SLOT

    # (label, wram patches, expectations) per run
    daimyo_cases, province_cases = [], []
    for s in range(SCENARIO_COUNT):
        img = rom.scenario_image(s)
        for d in rom.daimyos(s):
            i = d["index"]
            daimyo_cases.append((s, d, [
                (d_at, rom.wram(img, DAIMYO_WRAM + DAIMYO_SIZE * i, DAIMYO_SIZE)),
                (s_at, rom.wram(img, SURNAMES_WRAM + SURNAME_SIZE * i, SURNAME_SIZE)),
                (g_at, rom.wram(img, GIVEN_WRAM + GIVEN_SIZE * i, GIVEN_SIZE))]))
        for p in rom.provinces(s):
            i = p["index"]
            province_cases.append((s, p, [
                (p_at, rom.wram(img, PROVINCES_WRAM + PROVINCE_SIZE * i, PROVINCE_SIZE)),
                (n_at, rom.wram(img, PROVINCE_NAMES_WRAM + PROVINCE_NAME_SIZE * i, PROVINCE_NAME_SIZE))]))
    runs, expect = [], []
    for k in range(max(len(daimyo_cases), len(province_cases))):
        wram, exp = [], {"kind": "data"}
        if k < len(daimyo_cases):
            s, d, patch = daimyo_cases[k]
            wram += patch
            exp["daimyo"] = (s, d, rom.codes(patch[1][1]) + rom.codes(patch[2][1]))
        if k < len(province_cases):
            s, p, patch = province_cases[k]
            wram += patch
            exp["province"] = (s, p, rom.codes(patch[1][1]))
        runs.append(wram)
        expect.append(exp)
    # made-up values: every shown field different
    for base in (11, 500):
        vals = {k: base + 37 * i for i, (k, _) in enumerate(PROVINCE_FIELDS)}
        stats = {"age": base % 100 + 3, **{k: (base + 13 * (i + 1)) % 250 for i, (k, _) in enumerate(DAIMYO_STATS)}}
        drec = bytes([stats["age"]] + [stats[k] for k, _ in DAIMYO_STATS] + [31, 0])
        runs.append([(p_at, record_bytes(vals, [k for k, _ in PROVINCE_FIELDS])), (d_at, drec)])
        expect.append({"kind": "synthetic", "values": {**vals, **stats}})
    # every glyph once
    for g0 in range(0, GLYPH_COUNT, 9):
        gl = list(range(g0, min(g0 + 9, GLYPH_COUNT)))
        gl += [g0] * (9 - len(gl))
        runs.append([(n_at, encode(gl[:4], PROVINCE_NAME_SIZE)), (s_at, encode(gl[4:7], SURNAME_SIZE)),
                     (g_at, encode(gl[7:9], GIVEN_SIZE))])
        expect.append({"kind": "text", "province": gl[:4], "daimyo": gl[4:9]})
    # the women's portraits
    for n in range(68, PORTRAIT_COUNT):
        runs.append([(d_at + 6, bytes([n]))])
        expect.append({"kind": "face", "face": n})

    reads = [("vram", 0, 0x4000), ("vram", 0xF800, 0x800), ("vram", FACE_VRAM, FACE_BYTES),
             ("cgram", FACE_CGRAM, 32)]
    results = replay(args.rom, TO_INFO, save_frame(TO_INFO),
                     [{"wram": w, "steps": STEPS, "shot": SHOT, "read": reads} for w in runs])

    face_pal = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    counts = {k: [0, 0] for k in ("daimyo", "province", "synthetic", "text", "face", "palette")}
    bad: dict[str, list] = {k: [] for k in counts}
    for exp, (chars, tmap, face, pal) in zip(expect, results):
        vram = bytearray(0x10000)
        vram[0:0x4000] = chars
        vram[0xF800:0x10000] = tmap
        sc = Screen(rom, vram)
        nums = {k: sc.number(x - WIDTH + 1, y, WIDTH) for k, (x, y) in NUMBERS.items()}
        counts["palette"][0] += 1
        if pal != face_pal:
            bad["palette"].append(len(bad["palette"]))
        if exp["kind"] == "data":
            if "daimyo" in exp:
                s, d, glyphs = exp["daimyo"]
                counts["daimyo"][0] += 1
                want = {"age": d["age"], **{k: d[k] for k, _ in DAIMYO_STATS}}
                got = {k: nums[k] for k in want}
                gl = sc.glyphs(*DAIMYO_NAME_AT, len(glyphs) + 1)
                if (got != want or gl != [c - CODE_BASE for c in glyphs]
                        or face != rom.face_raw(d["person"])):
                    bad["daimyo"].append((s + 1, d["index"], d["name"], got, want, gl))
            if "province" in exp:
                s, p, glyphs = exp["province"]
                counts["province"][0] += 1
                want = {k: p[k] for k in SHOWN_FIELDS}
                got = {k: nums[k] for k in want}
                gl = sc.glyphs(*PROVINCE_NAME_AT, len(glyphs) + 1)
                if got != want or gl != [c - CODE_BASE for c in glyphs]:
                    bad["province"].append((s + 1, p["index"], p["name"], got, want, gl))
        elif exp["kind"] == "synthetic":
            counts["synthetic"][0] += 1
            want = {k: v for k, v in exp["values"].items() if k in NUMBERS}
            got = {k: nums[k] for k in want}
            if got != want:
                bad["synthetic"].append((got, want))
        elif exp["kind"] == "text":
            counts["text"][0] += 1
            gp = sc.glyphs(*PROVINCE_NAME_AT, 4, stop_blank=False)
            gd = sc.glyphs(*DAIMYO_NAME_AT, 5, stop_blank=False)
            if gp != exp["province"] or gd != exp["daimyo"]:
                bad["text"].append((exp["province"] + exp["daimyo"], gp + gd))
        else:
            counts["face"][0] += 1
            if face != rom.face_raw(exp["face"]):
                bad["face"].append(exp["face"])
    labels = {
        "daimyo": "daimyo slots of the 4 scenarios: name glyphs, 年齢 and 健康 野心 運 魅力 知力, face = LZ 120 + person",
        "province": "provinces of the 4 scenarios: name glyphs and the 12 shown values",
        "synthetic": "runs with made-up values: every field on its own place",
        "text": "text runs (9 glyph codes each): all 636 glyphs drawn from code 0x8140 + g",
        "face": "person ids 68-72: face tiles = LZ stream 120 + id",
        "palette": "runs: OBJ palette 5 = ROM 0x7F796",
    }
    errors = 0
    for k, (n, _) in counts.items():
        ng = bad[k]
        errors += len(ng)
        print(f"[{k}] {n - len(ng)}/{n} {labels[k]}", flush=True)
        for b in ng[:8]:
            print("   NG", b)
    print(f"{'ALL OK' if not errors else 'PROBLEMS'} ({time.time() - t0:.0f} s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
