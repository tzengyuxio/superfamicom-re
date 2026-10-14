#!/usr/bin/env python3
"""Check the 713 person records (rom.Rom.persons) and the name table against the game (needs Mesen 2, about
6 minutes).

At the battle of 桶狭間 the 情報 command opens 木下藤吉郎's info screen (tools/sequences.TO_INFO). A savestate is
taken just before; for every record k the 54 bytes of record 0 at $7E:24A7 are replaced by record k (from the
start block, or from LATER_PERSONS for k >= 241) and the screen opened by the game's own code ($C6:C6xx):
- vprintf $C6:2E8B: "%s%s" ($C6:FE87) must get the name table pointers of person id +0 (+0 / +7 of entry id),
  "%6s" ($C6:FE83) the rank string of +25, "%6s軍" the name of the faction's daimyo (+23 -> faction +0 -> record
  -> id), 政略Lv ($C6:FE62) +30, 戦術Lv ($C6:FE6C) +33;
- the stat bars $C8:21D4 (called from $C6:C6E0-$C6:C7A6) must get +34 +36 +38 +35 +37 +39 (外交 魅力 武力 内政 統率
  野心);
- the skill grades ($CD:005D, returned at $C6:C7F9) must equal the 2-bit fields of +40 / +41 and their mean;
- the face at VRAM 0x2400 (640 bytes) must equal rom.Rom.face_tiles(name table face code), CGRAM 0x120 the
  face palette.

Usage: .venv/bin/python taikou/verify_persons.py [--rom ROM] [--quick]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
from replay import replay
from rom import (
    DEFAULT_ROM,
    FACE_BYTES,
    FACE_PALETTE,
    FACTION_COUNT,
    NAME_SIZE,
    NAMES,
    PERSON_COUNT,
    PERSON_TOTAL,
    PERSONS,
    STATS,
    STRING_TABLES,
    Rom,
    le16,
)
from sequences import TO_INFO, expand

SAVE_AT = 16340
STEPS = "w20 a:10"
SHOT = 140
FACE_VRAM, FACE_CGRAM = 0x2400, 0x120
FMTS = {"faction": 0xC6FE7D, "rank": 0xC6FE83, "name": 0xC6FE87, "政略Lv": 0xC6FE62,
        "戦術Lv": 0xC6FE6C}
EXTRA = """
local pf, bars, skills = {}, {}, {}
local fmts = {FMTS}
function EXTRA_RESET() pf = {}; bars = {}; skills = {} end
function EXTRA_SHOT()
  local out = {}
  for _, f in ipairs(fmts) do out[#out + 1] = pf[f] or "ffffffffffffffff" end
  for i = 1, 6 do out[#out + 1] = bars[i] or "ffff" end
  for i = 1, 8 do out[#out + 1] = skills[i] or "ff" end
  return table.concat(out)
end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local fmt = rd(sp + 4) + rd(sp + 5) * 256 + rd(sp + 6) * 65536
  local s = {}
  for i = 8, 15 do s[#s + 1] = string.format("%02x", rd(sp + i)) end
  if pf[fmt] == nil then pf[fmt] = table.concat(s) end
end, emu.callbackType.exec, 0xC62E8B, 0xC62E8B)
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local ret = rd(sp + 1) + rd(sp + 2) * 256 + rd(sp + 3) * 65536
  if ret >= 0xC6C6E0 and ret < 0xC6C7A6 and #bars < 6 then
    bars[#bars + 1] = string.format("%02x%02x", rd(sp + 6), rd(sp + 10))
  end
end, emu.callbackType.exec, 0xC821D4, 0xC821D4)
emu.addMemoryCallback(function()
  local d = emu.getState()["cpu.d"]
  if #skills < 8 then skills[#skills + 1] = string.format("%02x", rd(d)) end
end, emu.callbackType.exec, 0xC6C7F9, 0xC6C7F9)
""".replace("{FMTS}", "{" + ",".join(str(f) for f in FMTS.values()) + "}")


def ptr(raw: bytes, i: int) -> int:
    """24-bit pointer argument (the high byte of its bank word is junk) -> file offset."""
    return (raw[i] | raw[i + 1] << 8 | raw[i + 2] << 16) & 0x3FFFFF


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 713 名人物記錄與名稱表")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="only every 10th record")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    persons, factions = rom.persons(), rom.factions()
    ranks_base = STRING_TABLES["ranks"][0]
    ks = list(range(0, PERSON_TOTAL, 10 if args.quick else 1))
    read = [("vram", FACE_VRAM, FACE_BYTES), ("cgram", FACE_CGRAM, 32)]
    runs = [{"wram": [(PERSONS, rom.person_record(k))], "steps": STEPS, "shot": SHOT, "read": read} for k in ks]
    shots = replay(args.rom, expand(TO_INFO), SAVE_AT, runs, extra_lua=EXTRA)
    pal = rom.data[FACE_PALETTE:FACE_PALETTE + 32]
    keys = ["name", "rank", "faction", "政略Lv", "戦術Lv", "stats", "skills", "face", "palette"]
    bad: dict[str, list] = {k: [] for k in keys}
    skipped_faction = 0
    for k, (vram, cg, ex) in zip(ks, shots):
        p = persons[k]
        a = {name: ex[8 * i:8 * i + 8] for i, name in enumerate(FMTS)}
        bars = ex[8 * len(FMTS):8 * len(FMTS) + 12]
        skills = list(ex[8 * len(FMTS) + 12:8 * len(FMTS) + 20])
        name = NAMES + NAME_SIZE * p["id"]
        if [ptr(a["name"], 0), ptr(a["name"], 4)] != [name, name + 7]:
            bad["name"].append(k)
        rp = ranks_base + 3 * p["rank"]
        if ptr(a["rank"], 0) != int.from_bytes(rom.data[rp:rp + 3], "little") & 0x3FFFFF:
            bad["rank"].append(k)
        f = p["faction"]
        if f < FACTION_COUNT and factions[f]["daimyo"] < PERSON_COUNT:
            want = NAMES + NAME_SIZE * persons[factions[f]["daimyo"]]["id"]
            if ptr(a["faction"], 0) != want:
                bad["faction"].append(k)
        else:
            skipped_faction += 1
        for key in ("政略Lv", "戦術Lv"):
            if le16(a[key], 0) != p[key]:
                bad[key].append(k)
        order = [0, 2, 4, 1, 3, 5]  # screen rows: 外交 魅力 武力 内政 統率 野心
        if [bars[2 * i + 1] for i in range(6)] != [p[STATS[j]] for j in order]:
            bad["stats"].append(k)
        if skills != p["skills"]:
            bad["skills"].append(k)
        if vram != rom.face_tiles(p["face"]):
            bad["face"].append(k)
        if cg != pal:
            bad["palette"].append(k)
    n = len(ks)
    print(f"[persons] {n} records shown on 木下藤吉郎's 情報 screen by replacing record 0 with record k")
    labels = {"name": "名前 (name table entry of +0)", "rank": "身分 (+25 -> rank string)",
              "faction": f"所属 (+23 -> faction daimyo's name; {skipped_faction} without daimyo not checked)",
              "政略Lv": "政略Lv (+30)", "戦術Lv": "戦術Lv (+33)",
              "stats": "外交 内政 魅力 統率 武力 野心 (+34..+39)", "skills": "技能 8 grades (+40 / +41, 文化 = mean)",
              "face": "face tiles (name table face code -> face_tiles)", "palette": f"CGRAM 0x120 = 0x{FACE_PALETTE:X}"}
    for key in keys:
        print(f"  {labels[key]}: {n - len(bad[key])}/{n}" + (f" NG {bad[key][:10]}" if bad[key] else ""))
    errors = sum(len(v) for v in bad.values())
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
