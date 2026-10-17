#!/usr/bin/env python3
"""Check the horse tables in Mesen with the game's own horse card ($C3:360A, shown when a 4-year-old is offered at
the start, tools/w2.py horse_card; Program '96: $C4:4077, name build $CB:0AB4).

Every run writes the new-game blocks (rom.INIT_COPIES, the ROM bytes) back into WRAM, so the card reads the initial
tables, and a hook on the card entry replaces the horse id. The card prints (printf, traced at vsprintf):
age `%u歳`, sex `%s馬`, coat, farm `牧場　:%s`, sire `父 :%-9s`, dam `母 :%-9s` and damsire; the names come from
$C5:246C (name part + name part).

  racehorses   runs 0-119: horse k (slots 120-139 are empty); age / sex / coat / farm / sire / dam / damsire = rom.racehorses()
  stallions    the next runs: horse 0 with sire = stallion s (0-146) and dam = mare s % 140: the sire, dam and
               damsire names = rom.stallion_name / mare_name; the third name build (the damsire) is given racehorse
               s % 120's name parts, so its output checks the racehorse names too

Usage: .venv/bin/python winning2/verify_horses.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import w2  # noqa: I001 (puts tools/ on sys.path)
import printf_trace
from replay import end_frame, replay
from rom import DEFAULT_ROM, INIT_COPIES, INIT_WRAM_96, MARE_COUNT, RACEHORSE_SIZE, Rom

# card entry, name build, format addresses of the card (age, sex, coat, farm, sire, dam, damsire)
ADDR = {
    "original": {"card": 0xC3360A, "name": 0xC5246C, "fmt": [0xC3E6C1, 0xC3E6C6, 0xC3E6CB, 0xC3E6CE, 0xC3E6E0,
                                                            0xC3E6E9, 0xC3E6F7]},
    "program96": {"card": 0xC44077, "name": 0xCB0AB4, "fmt": [0xC4F58F, 0xC4F594, 0xC4F599, 0xC4F59C, 0xC4F5AE,
                                                             0xC4F5B7, 0xC4F5C5]},
}
FIELDS = ["age", "sex", "coat", "farm", "sire", "dam", "damsire"]

LUA = """
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
local function wr(a, v) emu.write(a, v, emu.memType.snesMemory) end
local names = 0
RESET_HOOKS[#RESET_HOOKS + 1] = function() names = 0 end
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  wr(sp + 4, PARAM(0)); wr(sp + 5, 0)
end, emu.callbackType.exec, @CARD@)
emu.addMemoryCallback(function()
  names = names + 1
  if names == 3 and PARAM(1) == 1 then
    local sp = emu.getState()["cpu.sp"]
    for i = 0, 3 do wr(sp + 4 + i, PARAM(2 + i)) end
  end
end, emu.callbackType.exec, @NAME@)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="用遊戲的馬卡片驗證現役馬、種牡馬、繁殖牝馬")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    if rom.version not in ADDR:
        raise SystemExit(f"{rom.version}: card addresses not known")
    a = ADDR[rom.version]
    t0 = time.time()
    init = [(INIT_WRAM_96[k] if rom.version == "program96" else w, rom.data[rom.o[k]:rom.o[k] + n])
            for k, w, n in INIT_COPIES]
    wram_horse = init[0][0]
    horses = rom.racehorses()
    stallions = rom.stallions()

    runs, expect = [], []
    for h in horses:
        runs.append({"wram": init + [(w2.WRAM_PARAM, bytes([h["index"], 0]))]})
        expect.append(("racehorse", h["index"], [str(h["age"]), h["sex"], h["coat"], h["farm_name"], h["sire_name"],
                                                 h["dam_name"], h["damsire_name"]]))
    for s in stallions:
        i, m, k = s["index"], s["index"] % MARE_COUNT, s["index"] % len(horses)
        rec = bytearray(init[0][1][:RACEHORSE_SIZE])
        rec[4], rec[5] = i, m
        p = rom.data[rom.o["RACEHORSE"] + RACEHORSE_SIZE * k:][:4]
        runs.append({"wram": init + [(wram_horse, bytes(rec)), (w2.WRAM_PARAM, bytes([0, 1]) + p)]})
        expect.append(("stallion", i, [None, None, None, None, rom.stallion_name(i), rom.mare_name(m),
                                       horses[k]["name"]]))
    for r in runs:
        r.update({"steps": "a:10 w200", "shot": 300, "read": []})

    lua = w2.COLLECT_LUA + w2.printf_lua(rom.version) + LUA.replace("@CARD@", str(a["card"])).replace("@NAME@", str(a["name"]))
    card = w2.horse_card(rom.version)
    res = replay(rom.path, card, end_frame(card), runs, extra_lua=lua)

    ng = {"racehorse": [], "stallion": []}
    ok = {"racehorse": 0, "stallion": 0}
    for (kind, idx, want), out in zip(expect, res):
        calls = {c["fmt"]: c["args"] for c in printf_trace.parse(out[-1])}
        got = []
        for f in a["fmt"]:
            args = calls.get(f, [])
            v = args[0] if args else None
            got.append(str(v) if isinstance(v, int) else rom.text_bytes(v) if v is not None else None)
        bad = [(FIELDS[j], w, g) for j, (w, g) in enumerate(zip(want, got)) if w is not None and w != g]
        if bad:
            ng[kind].append((idx, bad))
        else:
            ok[kind] += 1
    print(f"[racehorses] {ok['racehorse']}/{len(horses)} age / sex / coat / farm / sire / dam / damsire = card"
          + (f" NG {ng['racehorse'][:5]}" if ng["racehorse"] else ""))
    print(f"[stallions] {ok['stallion']}/{len(stallions)} stallion names, {MARE_COUNT} mare names, {len(horses)} "
          f"racehorse names (name build) = card" + (f" NG {ng['stallion'][:5]}" if ng["stallion"] else ""))
    errors = len(ng["racehorse"]) + len(ng["stallion"])
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
