#!/usr/bin/env python3
"""Check the scenario tables (rom.Rom.scenario_image and the table decoders) against the game (needs Mesen 2,
about 8 minutes per ROM).

One savestate at the scenario menu; one run per scenario (1-9) and side (日本軍 / 連合国軍) starts a new game
(tools/sequences.new_game) and plays on to the main screen. Lua hooks record
1. WRAM $7E:205A-$7E:5B0A when the scenario loader $0B:9A5A returns ($0B:A438): it must equal
   Rom.scenario_image(sc) byte for byte, except the bytes the game sets at run time (RUNTIME: scenario number,
   player count, 7 bytes after the misc block);
2. the arguments of the first vprintf ($06:BD03) of each format of the fleet panel of the main screen, and the
   LZ streams ($00:9896) loaded after the scenario. They must agree with the decoded tables: side name, fleet
   number, flagship type name and ship name (ship +3, +0), position (fleet +0/+2) or base name when the fleet is
   in port (fleet +8), fuel (fleet +C), morale and fatigue (fleet +11/+12), top speed = the slowest ship of the
   fleet (ships whose +4 is the fleet number, speed +8; 20 knots with transports), 戦闘機 / 攻撃機 / 偵察機 (sum
   of ship +A / +B / +C), 兵員 (sum of ship +D and of the troop ships' loads, fleet +18-+1B) / 兵員輸送船 (fleet
   +18-+1B with bit 7) / 燃料輸送船 (fleet +17); the only picture loaded must be the flagship's
   (Rom.ship_picture_entry of ship +13) at sea, one scene picture (entries 167-185) in port.
   連合国軍 in scenario 2 starts with the Pearl Harbor battle and does not reach the panel (WRAM only).

Usage: .venv/bin/python teitoku/verify_scenarios.py [--rom ROM] [--scenarios 1,2,...]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import rom as R
from replay import replay
from sequences import TO_SCENARIOS, end_frame, new_game

LO, HI = R.DATA_START, 0x5B0B  # initialised data through the country table
RUNTIME = {0x205B, 0x205F, *range(0x2B9A, 0x2BA1)}
SIDE_FMT, NUM_FMT, MORALE_FMT = 0x0AEACB, 0x0AEAD1, 0x07F3F4
SHIP_FMT, BASE_FMT, POS_FMT, SPEED_FMT, AIR_FMT = 0x0EEEE5, 0x0EEEF2, 0x0EEEF5, 0x0EEF05, 0x0EEF22
TROOP_FMT = 0x0EEF37
# runs whose new game does not reach the main screen with new_game's presses
NO_PANEL = {(2, 1): "連合国軍 starts with the attack on Pearl Harbor, a battle screen"}
FMTS = [SIDE_FMT, NUM_FMT, MORALE_FMT, SHIP_FMT, BASE_FMT, POS_FMT, SPEED_FMT, AIR_FMT, TROOP_FMT]

EXTRA = """
local FMTS = {@FMTS@}
local MAP = {@MAP@}
local dump, recs, lzs = nil, {}, {}
function EXTRA_RESET() dump = nil; recs = {}; lzs = {} end
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
emu.addMemoryCallback(function()
  if dump then return end
  local t = {}
  for a = @LO@, @HI@ - 1 do t[#t + 1] = string.format("%02x", emu.read(a, emu.memType.snesWorkRam, false)) end
  dump = table.concat(t)
end, emu.callbackType.exec, 0x0BA438)
emu.addMemoryCallback(function()
  if dump and #lzs < 64 then lzs[#lzs + 1] = string.format("%06x", rd(0x56) | rd(0x57) << 8 | rd(0x58) << 16) end
end, emu.callbackType.exec, 0x009896)
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local fmt = rd(sp + 4) | rd(sp + 5) << 8 | rd(sp + 6) << 16
  fmt = MAP[fmt] or fmt
  if recs[fmt] ~= nil then return end
  local va = rd(sp + 8) | rd(sp + 9) << 8
  local u = {}
  for i = 0, 15 do u[#u + 1] = string.format("%02x", rd(va + i)) end
  recs[fmt] = table.concat(u)
end, emu.callbackType.exec, 0x06BD03)
function EXTRA_SHOT()
  local out = {dump or string.rep("00", @HI@ - @LO@)}
  for _, f in ipairs(FMTS) do out[#out + 1] = recs[f] or string.rep("ff", 16) end
  out[#out + 1] = table.concat(lzs) .. string.rep("ffffff", 64 - #lzs)
  return table.concat(out)
end
""".replace("@FMTS@", ",".join(map(str, FMTS))).replace("@LO@", str(LO)).replace("@HI@", str(HI))


def check_panel(rom: R.Rom, sc: int, side: int, recs: dict, pictures: list[int]) -> tuple[list[str], str]:
    img = rom.scenario_image(sc)
    ships, fleets = rom.ships(sc), rom.fleets(sc)
    errors = []
    p24 = lambda raw, o: int.from_bytes(raw[o:o + 3], "little")
    w16 = lambda raw, o: R.le16(raw, o)
    if p24(recs[SIDE_FMT], 0) != 0x7E0000 + R.SIDES + R.SIDE_SIZE * side + 1:
        errors.append("side name")
    num = w16(recs[NUM_FMT], 0)
    fl = next((f for f in fleets if f["side"] == side and f["number"] == num), None)
    if fl is None:
        return [f"no fleet {num}"], ""
    flag = ships[fl["flagship"]]
    rec = img[R.SHIPS + R.SHIP_SIZE * flag["id"]:]
    if p24(recs[SHIP_FMT], 0) != rom.ptr(R.SHIP_TYPE_NAMES + 3 * flag["type"]) or p24(recs[SHIP_FMT], 4) != p24(rec, 0):
        errors.append("flagship type/name")
    if recs[POS_FMT] is not None and (w16(recs[POS_FMT], 0), w16(recs[POS_FMT], 2)) != (fl["x"], fl["y"]):
        errors.append("position")
    if recs[BASE_FMT] is not None:
        b = img[R.BASES + R.BASE_SIZE * fl["base"]:]
        if p24(recs[BASE_FMT], 0) != p24(b, 1):
            errors.append("base")
    if recs[POS_FMT] is None and recs[BASE_FMT] is None:
        errors.append("no position")
    members = [s for s in ships if s["side"] == side and s["fleet"] == num]
    top = min([s["speed"] for s in members] + [R.TRANSPORT_SPEED] * bool(fl["fuel_ships"] or fl["troop_ships"]))
    if w16(recs[SPEED_FMT], 2) != top or R.le32(recs[SPEED_FMT], 4) != fl["fuel"]:
        errors.append(f"speed/fuel {w16(recs[SPEED_FMT], 2)}/{R.le32(recs[SPEED_FMT], 4)} vs "
                      f"{[s["speed"] for s in members]}/{fl["fuel"]}")
    if [w16(recs[AIR_FMT], 2 * k) for k in range(3)] != [sum(s[k] for s in members)
                                                          for k in ("fighters", "attackers", "scouts")]:
        errors.append("aircraft")
    if (w16(recs[MORALE_FMT], 0), w16(recs[MORALE_FMT], 2)) != (fl["morale"], fl["fatigue"]):
        errors.append("morale/fatigue")
    troops = [sum(s["troops"] for s in members) + sum(fl["troop_ships"]), len(fl["troop_ships"]), fl["fuel_ships"]]
    if recs[TROOP_FMT] is None or [w16(recs[TROOP_FMT], 2 * k) for k in range(3)] != troops:
        errors.append("troops/transports")
    entry_of = {rom.ptr(rom.off["entries"] + 3 * e): e for e in range(R.ENTRY_COUNT)}
    pics = [entry_of[p] for p in pictures]
    if recs[BASE_FMT] is not None:  # in port: a scene picture instead of the flagship
        where = f"in port {rom.bases(sc)[fl['base']]['code']}, scene picture {pics}"
        if len(pics) != 1 or not R.SCENE_FIRST_ENTRY <= pics[0] < R.SCENE_FIRST_ENTRY + R.SCENE_COUNT:
            errors.append(f"pictures {pics}")
    else:
        where = f"at sea, ship picture {pics}"
        if pics != [rom.ship_picture_entry(flag["class"])]:
            errors.append(f"pictures {pics} != {rom.ship_picture_entry(flag['class'])}")
    return errors, f"{fl['number']}艦隊 {flag['type_name']} {flag['name']} ({len(members)} 隻, {where})"


def main() -> None:
    ap = argparse.ArgumentParser(description="劇本資料表與遊戲比對")
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--scenarios", default="1,2,3,4,5,6,7,8,9")
    args = ap.parse_args()
    t0 = time.time()
    rom = R.Rom(args.rom)
    cases = [(sc, side) for sc in map(int, args.scenarios.split(",")) for side in (0, 1)]
    save_at = end_frame(TO_SCENARIOS)
    runs = []
    for sc, side in cases:
        steps = new_game(sc, side)
        runs.append({"steps": steps, "shot": end_frame(steps, 0) + 300, "read": []})
    res = replay(args.rom, TO_SCENARIOS, save_at, runs, extra_lua=EXTRA.replace("@MAP@", rom.lua_string_map(FMTS)))
    n = HI - LO
    bad = 0
    picture_srcs = {rom.ptr(rom.off["entries"] + 3 * e) for e in range(54, R.SCENE_FIRST_ENTRY + R.SCENE_COUNT)}
    for (sc, side), (out,) in zip(cases, res):
        dump = out[:n]
        img = rom.scenario_image(sc)
        diff = [a for a in range(LO, HI) if a not in RUNTIME and img[a] != dump[a - LO]]
        recs = {}
        for k, f in enumerate(FMTS):
            raw = out[n + 16 * k:n + 16 * (k + 1)]
            recs[f] = None if raw == b"\xff" * 16 else raw
        lz = out[n + 16 * len(FMTS):]
        pictures = [p for p in (int.from_bytes(lz[k:k + 3], "big") for k in range(0, len(lz), 3)) if p in picture_srcs]
        if recs[SHIP_FMT]:
            errors, what = check_panel(rom, sc, side, recs, pictures)
        elif (sc, side) in NO_PANEL:
            errors, what = [], f"not reached ({NO_PANEL[sc, side]})"
        else:
            errors, what = ["no fleet panel"], ""
        if diff:
            errors.insert(0, f"WRAM {len(diff)} bytes differ ({', '.join(f'{a:04X}' for a in diff[:8])})")
        bad += bool(errors)
        print(f"[scenario {sc} {R.SIDE_NAMES[side]}] WRAM {LO:04X}-{HI - 1:04X}: {n - len(diff) - len(RUNTIME)}"
              f"/{n - len(RUNTIME)} bytes equal; panel {what}: " + ("OK" if not errors else "NG " + "; ".join(errors)))
    print(f"{len(cases) - bad}/{len(cases)} runs OK ({time.time() - t0:.0f} s)")
    print("ALL OK" if not bad else f"{bad} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
