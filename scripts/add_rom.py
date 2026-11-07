"""Put a ROM zip into the only place ROMs are kept, ~/game-library/_original/sfc/ (~/.claude/re-common.md §11), and
record its sha1 and the sha1 of each file inside in SHA1SUMS.txt there.

Usage: .venv/bin/python scripts/add_rom.py ZIP...      (No-Intro names; a ZIP already there is re-hashed)
"""
import hashlib
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from paths import ORIGINAL


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def add_rom(rom: str) -> None:
    os.makedirs(ORIGINAL, exist_ok=True)
    name = os.path.basename(rom)
    dst = os.path.join(ORIGINAL, name)
    if os.path.abspath(rom) != os.path.abspath(dst):
        shutil.copy2(rom, dst)
    lines = []
    with zipfile.ZipFile(dst) as z:
        for i in z.infolist():
            lines.append(f"{sha1(z.read(i))}  {name}/{i.filename}")
    with open(dst, "rb") as f:
        lines.append(f"{sha1(f.read())}  {name}")
    sums = os.path.join(ORIGINAL, "SHA1SUMS.txt")
    old = []
    if os.path.exists(sums):
        with open(sums, encoding="utf-8") as f:
            old = f.read().splitlines()
    keep = [x for x in old if x.split("  ", 1)[1].split("/")[0] != name]  # replace this ROM's lines
    with open(sums, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(keep + lines, key=lambda x: x.split("  ", 1)[1])) + "\n")


if __name__ == "__main__":
    for rom in sys.argv[1:]:
        add_rom(rom)
        print(f"{os.path.basename(rom)} -> {ORIGINAL}")
