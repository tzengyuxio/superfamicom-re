#!/usr/bin/env python3
"""Check the faces (11 files, 96 frames, FACEPAL) against the game in Mesen.

Savestate right after NEW GAME, just before the secretary's first face ($05:8768 -> $01:B0D8("HISHO", ..., x 5,
y 2, frame 1)). In every run the call's file-name pointer (S+4), frame (S+18) and tile slot (S+20) are replaced
by one frame of one face file (a Lua exec hook at $01:B0D8, values passed through WRAM $E000). The game then
decompresses the file and draws the frame; checked:
1. the 24 tiles in VRAM at the frame's first tile number * 32 = rom.face_tiles;
2. the 4 x 6 tilemap words at BG $E800 (x 5, y 2) = rom.face_tilemap;
3. CGRAM row 2 = FACEPAL (colour 0 excluded: backdrop);
4. the hook saw the replaced call (file name, frame).
Run 0 leaves the game alone: its own call must be HISHO frame 1.

Usage: .venv/bin/python topman2/verify_faces.py [--rom ROM]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
import tm2
from replay import end_frame, replay
from rom import DEFAULT_ROM, FACE_NAME_ADDR, FACE_TILEMAP, Rom

BOOT = tm2.TITLE + " a:10"     # NEW GAME; the secretary's face is drawn at ~1598
SAVE = end_frame(BOOT) + 2
SHOT = 150                      # the next face is drawn at ~1839
X, Y = 5, 2
PATCH_LUA = """
local function patch_hook()
  local function rd(a) return emu.read(a, emu.memType.snesWorkRam) end
  if rd(0xE000) ~= 1 then return end
  local s = emu.getState()["cpu.sp"]
  local p = emu.read(s + 4, emu.memType.snesMemory, false) | emu.read(s + 5, emu.memType.snesMemory, false) << 8
  if p ~= 0xD372 then return end
  emu.write(s + 4, rd(0xE001), emu.memType.snesMemory)
  emu.write(s + 5, rd(0xE002), emu.memType.snesMemory)
  emu.write(s + 18, rd(0xE003), emu.memType.snesMemory)
  emu.write(s + 19, 0, emu.memType.snesMemory)
  emu.write(s + 20, rd(0xE004), emu.memType.snesMemory)
  emu.write(s + 21, 0, emu.memType.snesMemory)
  emu.write(0x7EE000, 0, emu.memType.snesMemory)
end
emu.addMemoryCallback(patch_hook, emu.callbackType.exec, 0x01B0D8)
emu.addMemoryCallback(patch_hook, emu.callbackType.exec, 0x81B0D8)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    t = time.time()
    faces = rom.faces()
    tm_reads = [("vram", FACE_TILEMAP + 2 * ((Y + r) * 32 + X), 8) for r in range(6)]
    runs = [{"shot": SHOT, "read": [("cgram", 64, 32)]}]
    for f in faces:
        t0 = rom.face_tilemap(f["file"], f["frame"])[0] & 0x3FF
        a = FACE_NAME_ADDR[f["file"]]
        runs.append({"wram": [(tm2.PARAM, bytes([1, a & 0xFF, a >> 8, f["frame"], t0]))], "shot": SHOT,
                     "read": [("vram", t0 * 32, 768)] + tm_reads})
    res = replay(rom.path, BOOT, SAVE, runs, extra_lua=tm2.COLLECT_LUA + PATCH_LUA + tm2.FACE_LUA)
    bad = 0
    own = tm2.faces(tm2.parse(res[0][-1]))
    pal = rom.raw("FACEPAL")
    ok0 = own[:1] == [(FACE_NAME_ADDR["HISHO"], 1, X, Y)]
    okp = res[0][0][2:] == pal[2:]
    print(f"[game] own call HISHO frame 1 at (5, 2): {'OK' if ok0 else 'NG ' + str(own[:2])}; "
          f"CGRAM row 2 = FACEPAL: {'OK' if okp else 'NG'}")
    bad += (not ok0) + (not okp)
    stats = {}
    for f, r in zip(faces, res[1:]):
        tiles_ok = r[0] == rom.face_tiles(f["file"], f["frame"])
        tm = [int.from_bytes(r[1 + k][2 * c:2 * c + 2], "little") for k in range(6) for c in range(4)]
        tm_ok = tm == rom.face_tilemap(f["file"], f["frame"])
        call_ok = tm2.faces(tm2.parse(r[-1]))[:1] == [(FACE_NAME_ADDR[f["file"]], f["frame"], X, Y)]
        s = stats.setdefault(f["file"], [0, 0])
        s[1] += 1
        if tiles_ok and tm_ok and call_ok:
            s[0] += 1
        else:
            bad += 1
            print(f"  NG {f['file']} frame {f['frame']}: tiles {tiles_ok} tilemap {tm_ok} call {call_ok}")
    for name, (ok, n) in stats.items():
        print(f"  {name}: {ok}/{n}")
    print(f"[frames] tiles, tilemap and call = ROM: {sum(ok for ok, _ in stats.values())}/{len(faces)}")
    print(f"{'OK' if not bad else f'{bad} problem(s)'} ({time.time() - t:.0f} s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
