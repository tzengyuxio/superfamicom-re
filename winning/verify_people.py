#!/usr/bin/env python3
"""Check trainers, their jockeys, and the person name table (256 surnames / given names) in Mesen.

From the savestate before the trainer list (tools/wp.TRAINER_LIST), the presses open trainer 0's
info window ($CB:77C2; the trainer number is the local at S+1, replaced at $CB:77D7 for every run). The window
prints, through vprintf $C2:1E9A, the trainer's surname and given name ($CB:EF1D / EF23, built in WRAM $C101),
the jockey ($CB:EF26 / EF37) and six traits ($CB:EF3E ...). The faces are not drawn by $CA:2DA7 here: the list
page loads the faces of its 8 trainers into VRAM $A800 + 0x3C0 * row (30 tiles each).
1. all 30 trainers: names, jockey = jockey 20 + record byte 2 (person = the jockey record's byte 21),
   traits = bits 0-5 of record byte 5 (rom.TRAINER_TRAITS); face: trainer 0's face word (record bytes 0-1) is
   patched in ROM to trainer t's, and the 960 bytes at VRAM $A800 must be rom.face_bytes of it;
2. all 256 persons: trainer 0's jockey byte is set to 0 (ROM patch) and jockey 20's person bytes 20-21 in WRAM
   ($2301 + 20) to the person under test; the printed jockey surname / given name must be rom.person.

Usage: .venv/bin/python winning/verify_people.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import wp
from replay import end_frame, replay
from rom import DEFAULT_ROM, FACE_BYTES, PERSON_COUNT, TRAINER_COUNT, TRAINER_TRAITS, WRAM_JOCKEY_B, Rom

BOOT = wp.TRAINER_LIST
# secretary's question, list, trainer 0's window: three presses in a plain run, four in replay (one is not taken)
STEPS, SHOT = "a:10 w200" + wp.A200 * 3, 900
FORMATS = {"surname": 0xBEF1D, "given": 0xBEF23, "jockey_surname": 0xBEF26, "jockey_given": 0xBEF37}
VRAM_LIST_FACE = 0xA800          # face of the list's first row
TRAIT_FORMATS = [0xBEF3E, 0xBEF5D, 0xBEF84, 0xBEFA8, 0xBEFD2, 0xBEFF6]
OVERRIDE_LUA = """
emu.addMemoryCallback(function()
  REC_ADD("H")
  if PARAM(2) == 0 then return end
  emu.write(emu.getState()["cpu.sp"] + 1, PARAM(0), emu.memType.snesMemory)
end, emu.callbackType.exec, 0xCB77D7)
"""


def cstr(rom: Rom, o: int) -> bytes:
    return rom.data[o:rom.data.index(b"\0", o)]


def window(rom: Rom, raw: bytes) -> dict:
    """The strings the info window printed after the trainer number was read, by format (the first print of each)."""
    recs = wp.parse(raw)
    if ["H"] not in recs:
        return {}
    recs = recs[recs.index(["H"]):]
    fmts = {k: cstr(rom, o) for k, o in FORMATS.items()}
    fmts.update({f"trait{i}": cstr(rom, o) for i, o in enumerate(TRAIT_FORMATS)})
    out = {}
    for p in wp.prints(recs):
        for k, f in fmts.items():       # surname and given name share the format "%s": first one = surname
            if p["fmt"] == f and k not in out:
                out[k] = rom.text_bytes(p["s0"]).rstrip("　 ")
                break
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證調教師、騎手與人名表")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t0 = time.time()
    trainers, jockeys = rom.trainers(), rom.jockeys()
    runs = []
    for t in range(TRAINER_COUNT):
        runs.append({"steps": STEPS, "shot": SHOT, "read": [("vram", VRAM_LIST_FACE, FACE_BYTES)],
                     "patch": [(rom.o["TRAINER"], rom.data[rom.o["TRAINER"] + 22 * t:][:2])],
                     "wram": [(wp.WRAM_PARAM, bytes([t, 0, 1]))]})
    patch = [(rom.o["TRAINER"] + 2, b"\0")]
    for p in range(PERSON_COUNT):
        runs.append({"steps": STEPS, "shot": SHOT, "read": [], "patch": patch,
                     "wram": [(wp.WRAM_PARAM, bytes([0, 0, 1])), (WRAM_JOCKEY_B + 20, bytes([p, p]))]})
    res = replay(rom.path, BOOT, end_frame(BOOT), runs, extra_lua=wp.COLLECT_LUA + wp.PRINT_LUA + OVERRIDE_LUA)
    errors = 0
    bad = []
    for t, r in zip(trainers, res[:TRAINER_COUNT]):
        w = window(rom, r[-1])
        j = jockeys[t["jockey"]]
        want = {"surname": t["surname"], "given": t["given"], "jockey_surname": j["surname"],
                "jockey_given": j["given"]}
        want.update({f"trait{i}": TRAINER_TRAITS[i][t["traits"] >> i & 1] for i in range(6)})
        diff = {k: (w.get(k), v) for k, v in want.items() if w.get(k) != v}
        if r[0] != rom.face_bytes(t["face"]):
            diff["face"] = f"{t['face']:02X}"
        if diff:
            bad.append((t["index"], diff))
    print(f"[trainers] {TRAINER_COUNT - len(bad)}/{TRAINER_COUNT}: names, face, jockey, 6 traits"
          + (f" (NG {bad[:3]})" if bad else ""))
    errors += len(bad)
    bad = []
    for p, r in zip(range(PERSON_COUNT), res[TRAINER_COUNT:]):
        w = window(rom, r[-1])
        if (w.get("jockey_surname"), w.get("jockey_given")) != rom.person(p):
            bad.append((p, w.get("jockey_surname"), w.get("jockey_given"), rom.person(p)))
    print(f"[persons] {PERSON_COUNT - len(bad)}/{PERSON_COUNT} surname / given name = rom.person"
          + (f" (NG {bad[:5]})" if bad else ""))
    errors += len(bad)
    print(f"time {time.time() - t0:.0f}s")
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
