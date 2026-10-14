#!/usr/bin/env python3
"""Check the faces (SECRET / STAFF / MAKER / MAYOR, FACEPAL) and the game's face descriptors in Mesen.

Part A — scenario 1, Berlin, savestate just before the secretary's first message ($84:AD20 draws the face of
the descriptor at WRAM $28C5):
1. every image of the 4 face files: the descriptor is replaced by (kind, image, palette); the 960 bytes the
   game puts in VRAM ($0000 for SECRET / STAFF, $0800 for MAKER / MAYOR) and the CGRAM row 4 it loads must
   equal rom.face_bytes / rom.face_palette (colour 0 excluded: transparent).
   The runs go through the palettes 0-29 so every FACEPAL palette is checked once;
2. the descriptors the game made at the start for the 4 players' secretaries ($28C5) and staff ($28D5): kind,
   image range and palette = area base + 0..3 ($82:AF85 / $82:B0A0, home city in the player record $2541);
3. country representatives (file MAYOR): the secretary's face call is redirected (PRG patch, stub in WRAM
   $7E:F000) to the game's representative window $8C:8634(city); the descriptor it builds (logged at the face
   routine $04:8199) must be rom.mayor_face(city) for all 89 cities, and the window's '％ｓ代表' must name the
   city's country. Then city 0's country byte ($2CBD) is set to each of the 57 countries in turn: the face
   image (country % 5) and the printed country name ($05:E5CB, converted to full width) are checked for all.
Part B — the aircraft spec screen (verify_aircraft.py's savestate) greets the player with the maker's face
($86:C77A: descriptor $05:EEC7[maker]); the maker number on the stack is replaced at $86:C77A by each of the 12
makers, and the logged descriptor and the drawn pixels / palette are compared.

Usage: .venv/bin/python airmanage2/verify_faces.py [--rom ROM]
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import am2
from replay import replay
from rom import (
    AREA_PAL_BASE,
    CITY_COUNT,
    COUNTRY_COUNT,
    DEFAULT_ROM,
    FACE_KINDS,
    FACE_PALETTES,
    MAKER_COUNT,
    WRAM_CITY,
    Rom,
    half_to_full,
    lorom,
)

STUB = 0xF000            # WRAM $7E:F000, unused (zero) in every dump of the game
PARAM = 0xF0F0           # per-run value for the Lua hooks
VRAM_AT = [0x0000, 0x0000, 0x0800, 0x0800]   # where the message window's face routine puts each kind's tiles
SECRETARY_CALL = (0x84, 0xAD20)   # PEA $0001 / PEA $0004 before the face call; 6 bytes replaced by JML + NOP NOP
MAKER_HOOK = """
local function maker_hook()
  local s = emu.getState()["cpu.sp"]
  local m = emu.read(0xF0F0, emu.memType.snesWorkRam)
  emu.write(s + 9, m, emu.memType.snesMemory)
  emu.write(s + 10, 0, emu.memType.snesMemory)
end
emu.addMemoryCallback(maker_hook, emu.callbackType.exec, 0x86C77A)
emu.addMemoryCallback(maker_hook, emu.callbackType.exec, 0x06C77A)
"""


def mayor_stub(city: int) -> bytes:
    """PEA 0, PEA 0, PEA $F100, PEA city, JSL $8C:8634 (the game's mayor window), then BRA to itself."""
    return bytes([0xF4, 0, 0, 0xF4, 0, 0, 0xF4, 0, 0xF1, 0xF4, city, 0, 0x22, 0x34, 0x86, 0x8C, 0x80, 0xFE])


def part_a(rom: Rom) -> int:
    images = [(k, i) for k in range(4) for i in range(rom.face_count(k))]
    # run 0 leaves the game alone: its own descriptors
    runs = [{"shot": 150, "read": [("wram", am2.PLAYER, 4 * 35), ("wram", am2.SECRETARY, 16),
                                   ("wram", am2.STAFF, 64), ("vram", 0, 960)]}]
    for n, (k, i) in enumerate(images):
        desc = bytes([k, 0, i, n % FACE_PALETTES])
        runs.append({"wram": [(am2.SECRETARY, desc)], "shot": 150,
                     "read": [("vram", VRAM_AT[k], 960), ("cgram", 0x80, 32)]})
    extra = [(FACE_PALETTES - 1, (0, 0))] if len(images) < FACE_PALETTES else []
    for p, (k, i) in extra:
        runs.append({"wram": [(am2.SECRETARY, bytes([k, 0, i, p]))], "shot": 150,
                     "read": [("vram", VRAM_AT[k], 960), ("cgram", 0x80, 32)]})
    jml = bytes([0x5C, STUB & 0xFF, STUB >> 8, 0x7E, 0xEA, 0xEA])
    for city in range(CITY_COUNT):
        runs.append({"patch": [(lorom(*SECRETARY_CALL), jml)], "wram": [(STUB, mayor_stub(city))], "shot": 400,
                     "read": []})
    for country in range(COUNTRY_COUNT):
        runs.append({"patch": [(lorom(*SECRETARY_CALL), jml)],
                     "wram": [(STUB, mayor_stub(0)), (WRAM_CITY, bytes([country]))], "shot": 400, "read": []})
    res = replay(rom.path, am2.BOOT_FACE, am2.FACE_SAVE_FRAME, runs,
                 extra_lua=am2.COLLECT_LUA + am2.FACE_LUA + am2.PRT_LUA)
    r0, res = res[0], res[1:]
    bad = 0
    # 1. pixels and palettes
    ok_img = ok_pal = 0
    pal_seen = set()
    for n, r in enumerate(res[:len(images) + len(extra)]):
        k, i = images[n] if n < len(images) else extra[n - len(images)][1]
        p = n % FACE_PALETTES if n < len(images) else extra[n - len(images)][0]
        ok_img += r[0] == rom.face_bytes(k, i)
        if r[0] != rom.face_bytes(k, i):
            drawn = am2.faces(am2.parse(r[-1]))
            hit = [(kk, ii) for kk in range(4) for ii in range(rom.face_count(kk)) if r[0] == rom.face_bytes(kk, ii)]
            print(f"  NG image {FACE_KINDS[k]} {i}: drawn {drawn[:1]}, VRAM holds {hit}")
        want_pal = rom.raw("FACEPAL")[32 * p:32 * p + 32]
        if r[1] == want_pal or r[1][2:] == want_pal[2:]:
            ok_pal += 1
            pal_seen.add(p)
    n_runs = len(images) + len(extra)
    print(f"[images] VRAM = ROM face: {ok_img}/{n_runs} "
          f"({', '.join(f'{f} {rom.face_count(k)}' for k, f in enumerate(FACE_KINDS))})")
    print(f"[palettes] CGRAM row 4 = FACEPAL: {ok_pal}/{n_runs}; palettes checked {len(pal_seen)}/{FACE_PALETTES}")
    bad += (n_runs - ok_img) + (n_runs - ok_pal) + (FACE_PALETTES - len(pal_seen))
    # 2. secretary / staff descriptors made by the game
    players, sec, stf = r0[0], r0[1], r0[2]
    drawn = am2.faces(am2.parse(r0[-1]))
    own = (sec[0], sec[2], sec[3])
    okd = int(drawn[:1] == [own] and r0[3] == rom.face_bytes(0, sec[2]))
    nd = 1
    print(f"  the game's own secretary face {own}: drawn {drawn[:1]}, VRAM = ROM {r0[3] == rom.face_bytes(0, sec[2])}")
    for pl in range(4):
        home = players[35 * pl + 1]
        base = AREA_PAL_BASE[rom.city_area(home)]
        d = sec[4 * pl:4 * pl + 4]
        nd += 1
        okd += d[0] == 0 and d[1] == 0 and d[2] < rom.face_count(0) and base <= d[3] < base + 4
        imgs = []
        for s in range(4):
            d = stf[16 * pl + 4 * s:16 * pl + 4 * s + 4]
            nd += 1
            okd += d[0] == 1 and d[1] == 0 and d[2] < 8 and base <= d[3] < base + 4
            imgs.append(d[2])
        nd += 1
        okd += len(set(imgs)) == 4
        print(f"  player {pl + 1}: home city {home} ({rom.cities()[home]['name_full']}), area base palette {base}, "
              f"secretary {tuple(sec[4 * pl:4 * pl + 4])}, staff images {imgs} palettes "
              f"{[stf[16 * pl + 4 * s + 3] for s in range(4)]}")
    print(f"[descriptors] secretary / staff kind, image range, palette = area base + 0..3, staff images distinct: "
          f"{okd}/{nd}")
    bad += nd - okd
    # 3. mayors
    countries = rom.countries()
    cities = rom.cities()

    def rep(r) -> tuple[list, list]:
        rec = am2.parse(r[-1])
        return am2.faces(rec), [p["s1"] for p in am2.prints(rec) if p["fmt"] == "％ｓ代表"]

    okm = 0
    for city, r in enumerate(res[n_runs:n_runs + CITY_COUNT]):
        got, names = rep(r)
        want_name = half_to_full(countries[cities[city]["country"]]["name"])
        if got[:1] == [rom.mayor_face(city)] and names[:1] == [want_name]:
            okm += 1
        else:
            print(f"  NG representative of city {city}: game {got[:1]} {names[:1]}, rom {rom.mayor_face(city)} "
                  f"{want_name}")
    print(f"[representatives] $8C:8634 descriptor (3, country % 5, area palette) and country name, per city: "
          f"{okm}/{CITY_COUNT}")
    okc = 0
    for country, r in enumerate(res[n_runs + CITY_COUNT:]):
        got, names = rep(r)
        want = (3, country % 5, rom.mayor_face(0)[2])
        want_name = half_to_full(countries[country]["name"])
        if got[:1] == [want] and names[:1] == [want_name]:
            okc += 1
        else:
            print(f"  NG country {country}: game {got[:1]} {names[:1]}, rom {want} {want_name}")
    print(f"[countries] face image = country % 5 and '％ｓ代表' = $05:E5CB name: {okc}/{COUNTRY_COUNT}")
    bad += CITY_COUNT - okm + COUNTRY_COUNT - okc
    return bad


def part_b(rom: Rom) -> int:
    makers = rom.makers()
    runs = [{"wram": [(PARAM, bytes([m["index"]]))], "shot": 150,
             "read": [("vram", 0x4800, 960), ("cgram", 0, 512)]} for m in makers]
    res = replay(rom.path, am2.SPEC, am2.SPEC_SAVE_FRAME, runs,
                 extra_lua=am2.COLLECT_LUA + am2.FACE_LUA + MAKER_HOOK)
    ok = 0
    for m, r in zip(makers, res):
        got = am2.faces(am2.parse(r[-1]))
        want = (m["face_kind"], m["face_image"], m["face_palette"])
        pal = rom.raw("FACEPAL")[32 * want[2] + 2:32 * want[2] + 32]
        good = got[:1] == [want] and r[0] == rom.face_bytes(2, want[1]) and any(
            r[1][32 * row + 2:32 * row + 32] == pal for row in range(16))
        ok += good
        print(f"  maker {m['index']} {m['name']}: game {got[:1]}, ROM {want} {'OK' if good else 'NG'}")
    print(f"[makers] $05:EEC7 descriptor, VRAM face and palette: {ok}/{MAKER_COUNT}")
    return MAKER_COUNT - ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--part", choices=["a", "b"], help=argparse.SUPPRESS)
    args = ap.parse_args()
    rom = Rom(args.rom)
    if args.part:
        bad = part_a(rom) if args.part == "a" else part_b(rom)
        print(f"PART_BAD {bad}")
        return
    t = time.time()
    procs = [subprocess.Popen([sys.executable, __file__, "--rom", args.rom, "--part", p], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True) for p in "ab"]
    bad = 0
    for p in procs:
        out = p.communicate()[0]
        for line in out.splitlines():
            if line.startswith("PART_BAD"):
                bad += int(line.split()[1])
            else:
                print(line)
        if "PART_BAD" not in out:
            bad += 1
            print("a part failed to run")
    print(f"{'OK' if not bad else f'{bad} problem(s)'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
