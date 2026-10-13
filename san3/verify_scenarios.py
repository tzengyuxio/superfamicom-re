#!/usr/bin/env python3
"""Check the scenario tables (rom.Rom.scenario_*) against the game's own loader (needs Mesen 2, ~1 minute).

For each of the 6 scenarios the game is started in Mesen (tools/mesen.py) and the scenario chosen; the
loader $C7:4F56 calls the table copiers $C7:4671 (header), $C7:46A4 (lists), $C7:49FF (persons),
$C7:4C19 (provinces), $C7:4DA4 (factions), $C7:4E80, $C7:4ED9 (item owners) and $C7:4F34. WRAM is read when
it reaches $C7:4FBD (all copiers done) and every field is compared with what the ROM tables predict:

  header      $2784, 33 bytes = SCENARIO_HEADER record
  items       $27A5 + 2 i = owner of item i
  provinces   $27BF + 49 k: +8 LE16 = rom +1, +A = 人口/100 (rom +3 x 100), +C 金 (rom +5 x 100),
              +E LE32 米 (rom +7 x 100), +12 勢力, +13..15 = rom +9..11, +1A 開発 = rom +12, +1C = rom +13,
              +1D 治水 = rom +14, +1E LE16 商業 = rom +15, +20 税率, +21 民忠, +22/24/26 LE16 = rom +19/21/23,
              +29..2B = rom +25..27
  factions    $30A3 + 47 k: +0 LE16 君主, +6 = rom +3, +D..21 = rom +4..24
  extra       $308D + i = SCEN_EXTRA[i * 6 + scenario]
  persons     $347E + 30 i (i < 531): +2 LE16 兵士 (rom +0 x 100), +4 LE16 item bits, +6 LE16 = person +2,
              +8 = 10 if the rank byte is FF, +A = person +4, +C rank & 7F (0 if FF), +D 相性, +E 義理, +F 忠誠,
              +10 province, +11 勢力 (the province's faction for ranks 0-4, else FF), +15 訓練 / +16 士気
              (scenario province +28/+29 for ranks 0-3 with soldiers, else 0). For rank byte FF the game takes
              +11/+15/+16 from "province FF" (out of the table), so those three are not compared.

勢力 of a province is the faction whose chain (faction +2 capital, province +0 next) reaches it.

Usage: .venv/bin/python san3/verify_scenarios.py [--rom ROM] [--dump DIR]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import Mesen
from rom import (
    DEFAULT_ROM,
    FACTION_COUNT,
    HEADER_SIZE,
    ITEM_COUNT,
    PROVINCE_COUNT,
    SCEN_EXTRA_COUNT,
    SCEN_PERSON_COUNT,
    SCENARIO_COUNT,
    Rom,
    le16,
)

NMI = 0x008392  # second instruction of the NMI handler ($8391 itself refuses savestates)
LOADED = 0xC74FBD
HEADER_AT, ITEMS_AT, EXTRA_AT = 0x2784, 0x27A5, 0x308D
PROV_AT, PROV_SIZE = 0x27BF, 49
FACT_AT, FACT_SIZE = 0x30A3, 47
PERS_AT, PERS_SIZE = 0x347E, 30
WRAM_LO, WRAM_HI = 0x2000, 0x7BFF  # copied out at $C7:4FBD

LUA = """
local boot={%(boot)s}
local runs={%(runs)s}
local f, sc, state, want_save, want_load = 0, 0, nil, false, false
local presses=boot
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(presses) do if f>=p[1] and f<p[1]+4 then inp[p[2]]=true end end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addMemoryCallback(function()  -- savestates only work inside exec callbacks: use the NMI handler
  if want_save then state=emu.createSavestate(); want_save=false; want_load=true; return end  -- load on a later NMI
  if want_load then
    want_load=false
    sc=sc+1
    if sc>#runs then emu.log("DONE"); emu.breakExecution(); return end
    emu.loadSavestate(state)
    f=%(menu)d
    presses=runs[sc]
  end
end, emu.callbackType.exec, %(nmi)d)
local loaded=false
emu.addMemoryCallback(function()  -- all scenario tables copied: log WRAM $lo-$hi
  if sc==0 then return end
  local out={}
  for a=%(lo)d,%(hi)d do out[#out+1]=string.format("%%02x", emu.read(0x7E0000+a, emu.memType.snesMemory)) end
  emu.log("WRAM " .. table.concat(out))
  loaded=true
end, emu.callbackType.exec, %(loaded)d)
emu.addEventCallback(function()
  f=f+1
  if f==%(menu)d and state==nil then want_save=true end
  if loaded then loaded=false; want_load=true; emu.breakExecution() end
end, emu.eventType.endFrame)
"""


def presses(steps: list[str], f: int) -> tuple[str, int]:
    out = []
    for st in steps:
        if st.startswith("w"):
            f += int(st[1:])
        else:
            out.append(f'{{{f},"{st}"}}')
            f += 24
    return ",".join(out), f


def scenario_wrams(rom_path: str) -> list[bytes]:
    """WRAM when the loader has copied every table, for scenarios 1-6 (title -> new game -> scenario list)."""
    boot, menu = presses(["w1200", "start", "w200", "start", "w300", "a", "w200"], 10)
    runs = []
    for sc in [0, *range(SCENARIO_COUNT)]:  # the first replay still runs from power-on: done twice, dropped
        lua, _ = presses(["w10", *["down", "w30"] * sc, "a"], menu)
        runs.append("{" + lua + "}")
    out = []
    lua = LUA % {"boot": boot, "runs": ",".join(runs), "menu": menu, "nmi": NMI, "loaded": LOADED,
                 "lo": WRAM_LO, "hi": WRAM_HI}
    with Mesen(rom_path) as m:
        m.run(lua, 300)
        while True:
            line = m.log().rstrip().rsplit("\n", 1)[-1]
            if line == "DONE":
                break
            out.append(bytes(WRAM_LO) + bytes.fromhex(line.split()[1]))
            m.resume(300)
    return out[1:]


def check(rom: Rom, sc: int, w: bytes) -> tuple[list[str], list[str]]:
    """(per-table 'ok/total' strings, mismatching fields)."""
    persons = rom.persons()
    owners = [it["owners"][sc] for it in rom.items()]
    pf = rom.province_factions(sc)
    provs = rom.scenario_provinces(sc)
    bad = []

    def cmp(table: str, idx: int, field: str, got: int, want: int) -> bool:
        if got != want:
            bad.append(f"{table}[{idx}].{field}: WRAM {got:#x} ROM {want:#x}")
            return False
        return True

    res = []
    hdr = rom.scenario_header(sc)["raw"]
    ok = cmp("header", 0, "raw", int.from_bytes(w[HEADER_AT:HEADER_AT + HEADER_SIZE], "big"), int.from_bytes(hdr, "big"))
    res.append(f"header {int(ok)}/1")
    ok = sum(cmp("items", i, "owner", le16(w, ITEMS_AT + 2 * i), owners[i]) for i in range(ITEM_COUNT))
    res.append(f"items {ok}/{ITEM_COUNT}")
    ext = rom.scenario_extra(sc)
    ok = sum(cmp("extra", i, "byte", w[EXTRA_AT + i], ext[i]) for i in range(SCEN_EXTRA_COUNT))
    res.append(f"extra {ok}/{SCEN_EXTRA_COUNT}")

    ok = 0
    for p in provs:
        k, r, o = p["id"], p["raw"], PROV_AT + PROV_SIZE * p["id"]
        fields = [("w8", le16(w, o + 8), le16(r, 1)), ("population", le16(w, o + 0xA), le16(r, 3) * 100),
                  ("gold", le16(w, o + 0xC), p["gold"]), ("food", int.from_bytes(w[o + 0xE:o + 0x12], "little"), p["food"]),
                  ("faction", w[o + 0x12], pf.get(k, 0xFF)), ("b13", w[o + 0x13], r[9]), ("b14", w[o + 0x14], r[10]),
                  ("b15", w[o + 0x15], r[11]), ("develop", w[o + 0x1A], r[12]), ("b1c", w[o + 0x1C], r[13]),
                  ("flood", w[o + 0x1D], r[14]), ("commerce", le16(w, o + 0x1E), p["commerce"]),
                  ("tax", w[o + 0x20], r[17]), ("loyalty", w[o + 0x21], r[18]), ("w22", le16(w, o + 0x22), le16(r, 19)),
                  ("w24", le16(w, o + 0x24), le16(r, 21)), ("w26", le16(w, o + 0x26), le16(r, 23)),
                  ("b29", w[o + 0x29], r[25]), ("b2a", w[o + 0x2A], r[26]), ("b2b", w[o + 0x2B], r[27])]
        ok += sum(not cmp("province", k, n, g, e) for n, g, e in fields) == 0  # compare every field
    res.append(f"provinces {ok}/{PROVINCE_COUNT}")

    ok = 0
    for fa in rom.scenario_factions(sc):
        k, r, o = fa["id"], fa["raw"], FACT_AT + FACT_SIZE * fa["id"]
        fields = [("ruler", le16(w, o), fa["ruler"])]
        if fa["ruler"] != 0xFFFF:
            fields += [("b3", w[o + 6], r[3]), ("rel", int.from_bytes(w[o + 0xD:o + 0x22], "big"),
                                                 int.from_bytes(r[4:25], "big"))]
        ok += sum(not cmp("faction", k, n, g, e) for n, g, e in fields) == 0  # compare every field
    res.append(f"factions {ok}/{FACTION_COUNT}")

    ok = 0
    for sp in rom.scenario_persons(sc):
        i, pr, o = sp["id"], persons[sp["id"]]["raw"], PERS_AT + PERS_SIZE * sp["id"]
        items = sum(1 << j for j, own in enumerate(owners) if own == i)
        absent = sp["rank_byte"] == 0xFF
        rank = 0 if absent else sp["rank"]
        fields = [("soldiers", le16(w, o + 2), sp["raw"][0] * 100), ("items", le16(w, o + 4), items),
                  ("w6", le16(w, o + 6), le16(pr, 2)), ("b8", w[o + 8], 0x10 if absent else 0), ("bA", w[o + 0xA], pr[4]),
                  ("rank", w[o + 0xC], rank), ("affinity", w[o + 0xD], pr[11]), ("duty", w[o + 0xE], pr[12]),
                  ("loyalty", w[o + 0xF], sp["loyalty"]), ("province", w[o + 0x10], sp["province"])]
        if not absent:  # rank byte FF: the game reads 勢力/訓練/士気 from province FF (garbage); not compared
            troops = rank < 4 and sp["soldiers"] != 0
            prov = provs[sp["province"]]["raw"] if troops else None
            fields += [("faction", w[o + 0x11], pf.get(sp["province"], 0xFF) if rank <= 4 else 0xFF),
                       ("training", w[o + 0x15], prov[28] if prov else 0), ("morale", w[o + 0x16], prov[29] if prov else 0)]
        ok += sum(not cmp("person", i, n, g, e) for n, g, e in fields) == 0  # compare every field
    res.append(f"persons {ok}/{SCEN_PERSON_COUNT}")
    return res, bad


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本資料（人物、州、勢力、寶物）")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dump", help="把每個劇本載入後的 WRAM 存到這個資料夾")
    ap.add_argument("--load", help="改讀 --dump 存下的 WRAM（不跑 Mesen）")
    args = ap.parse_args()
    t0 = time.time()
    rom = Rom(args.rom)
    if args.load:
        wrams = []
        for sc in range(SCENARIO_COUNT):
            with open(os.path.join(args.load, f"scenario{sc + 1}.wram"), "rb") as fh:
                wrams.append(fh.read())
    else:
        wrams = scenario_wrams(args.rom)
    errors = 0
    for sc, w in enumerate(wrams):
        if args.dump:
            os.makedirs(args.dump, exist_ok=True)
            with open(os.path.join(args.dump, f"scenario{sc + 1}.wram"), "wb") as fh:
                fh.write(w)
        res, bad = check(rom, sc, w)
        sel = w[0x7B19]
        errors += len(bad) + (sel != sc + 1)
        print(f"[scenario {sc + 1}] $7B19={sel}, " + ", ".join(res))
        for line in bad[:10]:
            print("   ", line)
    print(f"time {time.time() - t0:.0f} s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
