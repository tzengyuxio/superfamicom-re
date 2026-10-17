#!/usr/bin/env python3
"""Check the race table in Mesen with the game's own race functions, printed by the horse card ($C3:360A).

The card calls its accessors with the horse id it was given (S+4); a hook gives it race number r instead, and the
card's calls are patched (the JSL operands in $C3:364E-37CD) to the game's race functions:

  age `%u歳`      $C4:399C -> $C4:C7C8 distance in metres ($C1:BD27 x 100)
  sex `%s馬`      $C4:359B -> $C4:C803 race +2 bit 9 (0 / 1 print as 牡 / 牝: ダート / 芝)
  coat            $C4:3A9D -> $C4:C85A race +2 bits 14-15 (0-3 print as 白毛 芦毛 青毛 青鹿毛: ３歳 ... ５歳上)
  farm            $C4:3749 -> $C4:C48C class 0-8 (prints farm 0-8's name: 新馬 ... ＧⅠ)
  sire / damsire  $C4:2F7B, $C4:3036 + $C4:7442 -> $C1:3B3A (returns its argument), $C4:64A7 -> $C4:C60C long name
  dam             $C4:3036 -> $C1:3B3A, $C4:72F9 -> $C4:C66D short name

so one card checks a race's name number, long and short name, distance, surface, age condition and class (weight
rule, prize and the other bits are not checked). All 1147 race records (Program '96: the same card at $C4:4077 and
the same functions in bank $C7, 1162 records; race 0 is an empty record and is skipped).

Usage: .venv/bin/python winning2/verify_races.py [--rom ROM]
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
from rom import DEFAULT_ROM, Rom

ADDR = {
    "original": {
        "card": 0xC3360A,
        # JSL site -> new target
        "patch": {0xC3364E: 0xC4C7C8, 0xC33671: 0xC4C803, 0xC336AF: 0xC4C85A, 0xC336ED: 0xC4C48C,
                  0xC3374B: 0xC13B3A, 0xC33752: 0xC4C60C, 0xC33779: 0xC13B3A, 0xC33780: 0xC4C66D,
                  0xC337BF: 0xC13B3A, 0xC337C6: 0xC13B3A, 0xC337CD: 0xC4C60C},
        "fmt": {"distance": 0xC3E6C1, "surface": 0xC3E6C6, "age": 0xC3E6CB, "class": 0xC3E6CE, "name": 0xC3E6E0,
                "short": 0xC3E6E9, "name2": 0xC3E6F7},
    },
    # the same card at $C4:4077 and the same functions moved (identity $CE:098F, race functions in bank $C7)
    "program96": {
        "card": 0xC44077,
        "patch": {0xC440BB: 0xC70832, 0xC440DE: 0xC7086D, 0xC4411C: 0xC708C4, 0xC4415A: 0xC704EC,
                  0xC441B8: 0xCE098F, 0xC441BF: 0xC70676, 0xC441E6: 0xCE098F, 0xC441ED: 0xC706D7,
                  0xC4422C: 0xCE098F, 0xC44233: 0xCE098F, 0xC4423A: 0xC70676},
        "fmt": {"distance": 0xC4F58F, "surface": 0xC4F594, "age": 0xC4F599, "class": 0xC4F59C, "name": 0xC4F5AE,
                "short": 0xC4F5B7, "name2": 0xC4F5C5},
    },
}
LUA = """
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  emu.write(sp + 4, PARAM(0), emu.memType.snesMemory); emu.write(sp + 5, PARAM(1), emu.memType.snesMemory)
end, emu.callbackType.exec, @CARD@)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="用遊戲的比賽函式驗證比賽資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    if rom.version not in ADDR:
        raise SystemExit(f"{rom.version}: addresses not known")
    a = ADDR[rom.version]
    t0 = time.time()
    patch = [((site + 1) & 0x3FFFFF, (t & 0xFFFFFF).to_bytes(3, "little")) for site, t in a["patch"].items()]
    sex, coat, farms = rom.strings("sex"), rom.strings("coat"), [rom.farm_name(i) for i in range(9)]
    surfaces, ages, classes = rom.strings("surface"), rom.strings("age"), rom.strings("class")
    runs, expect = [], []
    for r in range(rom.o["RACE_COUNT"]):
        x = rom.race(r)
        if x["name_no"] == 0xFFFF:
            continue
        runs.append({"patch": patch, "wram": [(w2.WRAM_PARAM, r.to_bytes(2, "little"))],
                     "steps": "a:10 w200", "shot": 300, "read": []})
        expect.append((r, {"distance": str(x["distance"]), "surface": sex[surfaces.index(x["surface"])],
                       "age": coat[ages.index(x["age"])], "class": farms[classes.index(x["class"])],
                       "name": x["name"], "short": x["short"], "name2": x["name"]}))
    lua = w2.COLLECT_LUA + w2.printf_lua(rom.version) + LUA.replace("@CARD@", str(a["card"]))
    card = w2.horse_card(rom.version)
    res = replay(rom.path, card, end_frame(card), runs, extra_lua=lua)
    ng = []
    for (r, want), out in zip(expect, res):
        calls = {c["fmt"]: c["args"] for c in printf_trace.parse(out[-1])}
        got = {}
        for k, f in a["fmt"].items():
            v = (calls.get(f) or [None])[0]
            got[k] = str(v) if isinstance(v, int) else rom.text_bytes(v) if v is not None else None
        bad = {k: (want[k], got[k]) for k in want if want[k] != got[k]}
        if bad:
            ng.append((r, bad))
    print(f"[races] {len(runs) - len(ng)}/{len(runs)} name / short name / distance / surface / age / class = game"
          + (f" NG {ng[:4]}" if ng else ""))
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not ng else f"{len(ng)} problem(s)")
    raise SystemExit(1 if ng else 0)


if __name__ == "__main__":
    main()
