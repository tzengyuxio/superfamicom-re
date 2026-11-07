"""Copy one game's results into the game library (docs/backlog/game-archiving.md), so the repo's roms/ and output/
can be removed later.

Usage: .venv/bin/python scripts/archive.py GAME [--library DIR]   (default ~/game-library; run rebuild.py first)

What goes where, by file name (GAMES below gives each game's library id, ROMs and fragment folders):
  output/<file>                      -> <id>/<file>                 CSV, XLSX, PNG as they are
  output/<folder>/ of single images  -> <id>/<folder>.cbz           stored (not deflated) zip, one per folder
  output/music/                      -> <id>/music/                 as it is
  output/<folder>/ of anything else  -> <id>/<folder>/              the same rules, one level down
  output/portrait-sheet/*/out/*.png  -> <id>/sheets/                the rendered pages; manifests and copies dropped
  captures/                          -> <id>/captures/              as it is
  roms/<ROM>                         -> _original/<platform>/<ROM>  and its sha1 (and the sha1 of each file inside)
                                                                    in _original/<platform>/SHA1SUMS.txt
Fragment folders (no identity, an overview image already exists) are not kept. Files already in the library are
overwritten, nothing there is deleted. The library README.md of the game and the status table (koei.md, sfc.md)
are written by hand; the script only says when they are missing.
"""
import argparse
import hashlib
import os
import shutil
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLATFORM = "sfc"
# game folder -> library id (koei/... for KOEI games, sfc/... for the others), ROMs, fragment folders of output/
GAMES = {
    "san2": {"id": "koei/san2-sfc", "fragments": ["mob_parts"], "roms": [
        "Super Sangokushi II (Japan).zip",
        "Super Sangokushi II (Japan) (Rev 1).zip",
        "Romance of the Three Kingdoms II (USA).zip",
    ]},
    "san3": {"id": "koei/san3-sfc", "fragments": [], "roms": [
        "Sangokushi III (Japan).zip",
        "Sangokushi III (Japan) (Rev 1).zip",
        "Sangokushi III (Hong Kong).zip",
        "Romance of the Three Kingdoms III - Dragon of Destiny (USA).zip",
    ]},
    "san4": {"id": "koei/san4-sfc", "fragments": [], "roms": [
        "Sangokushi IV (Japan).zip",
        "Sangokushi IV (Japan) (Rev 1).zip",
        "Romance of the Three Kingdoms IV - Wall of Fire (USA).zip",
    ]},
    "sangokushi": {"id": "koei/san1-sfc", "fragments": [], "roms": [
        "Super Sangokushi (Japan).zip",
    ]},
    "eiketsu": {"id": "koei/eiketsu-sfc", "fragments": [], "roms": [
        "Sangokushi Eiketsuden (Japan).zip",
    ]},
    "kouryuuki": {"id": "koei/kouryuuki-sfc", "fragments": [], "roms": [
        "Kouryuuki (Japan).zip",
    ]},
    "zenkoku": {"id": "koei/nobu2-sfc", "fragments": [], "roms": [
        "Super Nobunaga no Yabou - Zenkoku Ban (Japan).zip",
        "Nobunaga's Ambition (USA).zip",
    ]},
    "bushou": {"id": "koei/nobu4-sfc", "fragments": ["mob_parts"], "roms": [
        "Super Nobunaga no Yabou - Bushou Fuuunroku (Japan).zip",
        "Super Nobunaga no Yabou - Bushou Fuuunroku (Japan) (Rev 1).zip",
    ]},
    "haouden": {"id": "koei/nobu5-sfc", "fragments": [], "roms": [
        "Nobunaga no Yabou - Haouden (Japan).zip",
        "Nobunaga no Yabou - Haouden (Japan) (Rev 1).zip",
        "Lord of Darkness (USA).zip",
    ]},
    "tenshouki": {"id": "koei/nobu6-sfc", "fragments": ["mob_parts"], "roms": [
        "Nobunaga no Yabou - Tenshouki (Japan).zip",
    ]},
    "taikou": {"id": "koei/taikoh-sfc", "fragments": [], "roms": [
        "Taikou Risshiden (Japan).zip",
    ]},
    "inindou": {"id": "koei/inindou-sfc", "fragments": [], "roms": [
        "Super Inindou - Datou Nobunaga (Japan).zip",
        "Inindo - Way of the Ninja (USA).zip",
    ]},
    "genchou": {"id": "koei/genchou-sfc", "fragments": [], "roms": [
        "Super Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).zip",
        "Genghis Khan II - Clan of the Gray Wolf (USA).zip",
    ]},
    "royal": {"id": "koei/royal-sfc", "fragments": [], "roms": [
        "Super Royal Blood (Japan).zip",
        "Gemfire (USA).zip",
    ]},
    "daikoukai": {"id": "koei/koukai-sfc", "fragments": ["mob_parts"], "roms": [
        "Super Daikoukai Jidai (Japan).zip",
        "Uncharted Waters (USA).zip",
    ]},
    "daikoukai2": {"id": "koei/koukai2-sfc", "fragments": [], "roms": [
        "Daikoukai Jidai II (Japan).zip",
        "New Horizons (USA).zip",
    ]},
    "dokuritsu": {"id": "koei/liberty-sfc", "fragments": [], "roms": [
        "Dokuritsu Sensou - Liberty or Death (Japan).zip",
        "Liberty or Death (USA).zip",
    ]},
    "europe": {"id": "koei/europe-sfc", "fragments": [], "roms": [
        "Europe Sensen (Japan).zip",
        "Operation Europe - Path to Victory 1939-45 (USA).zip",
    ]},
    "teitoku": {"id": "koei/tk-sfc", "fragments": [], "roms": [
        "Teitoku no Ketsudan (Japan).zip",
        "Teitoku no Ketsudan (Japan) (Rev 1).zip",
        "P.T.O. - Pacific Theater of Operations (USA).zip",
    ]},
    "teitoku2": {"id": "koei/tk2-sfc", "fragments": [], "roms": [
        "Teitoku no Ketsudan II (Japan).zip",
        "Teitoku no Ketsudan II (Japan) (Rev 1).zip",
        "P.T.O. II - Pacific Theater of Operations (USA).zip",
    ]},
    "airmanage": {"id": "koei/air-sfc", "fragments": [], "roms": [
        "Air Management - Oozora ni Kakeru (Japan).zip",
        "Air Management - Oozora ni Kakeru (Japan) (Rev 1).zip",
        "Aerobiz (USA).zip",
    ]},
    "airmanage2": {"id": "koei/air2-sfc", "fragments": [], "roms": [
        "Air Management II - Koukuu Ou o Mezase (Japan).zip",
        "Aerobiz Supersonic (USA).zip",
    ]},
    "topman2": {"id": "koei/topman2-sfc", "fragments": [], "roms": [
        "Top Management II (Japan).zip",
    ]},
    "leading": {"id": "koei/leading-sfc", "fragments": [], "roms": [
        "Leading Company (Japan).zip",
    ]},
    "winning": {"id": "koei/winning-sfc", "fragments": [], "roms": [
        "Winning Post (Japan).zip",
        "Winning Post (Japan) (Rev 1).zip",
    ]},
    "winning2": {"id": "koei/winning2-sfc", "fragments": [], "roms": [
        "Winning Post 2 (Japan).zip",
        "Winning Post 2 - Program '96 (Japan).zip",
        "Winning Post 2 - Program '96 (Japan) (Rev 1).zip",
    ]},
    "mahjong": {"id": "koei/mahjong-sfc", "fragments": [], "roms": [
        "Super Mahjong Taikai (Japan).zip",
    ]},
    "mahjong2": {"id": "koei/mahjong2-sfc", "fragments": [], "roms": [
        "Mahjong Taikai II (Japan).zip",
    ]},
    "yokoyama": {"id": "sfc/yokoyama-1", "fragments": [], "roms": [
        "Yokoyama Mitsuteru Sangokushi (Japan).zip",
        "Yokoyama Mitsuteru Sangokushi (Japan) (Rev 1).zip",
    ]},
}

IMAGES = (".png", ".gif", ".jpg")


def cbz(src: str, dst: str) -> int:
    names = sorted(n for n in os.listdir(src) if n != ".DS_Store")
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as z:
        for n in names:
            z.write(os.path.join(src, n), n)
    return len(names)


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def archive_rom(rom: str, dst_dir: str) -> None:
    os.makedirs(dst_dir, exist_ok=True)
    name = os.path.basename(rom)
    shutil.copy2(rom, os.path.join(dst_dir, name))
    lines = []
    with zipfile.ZipFile(rom) as z:
        for i in z.infolist():
            lines.append(f"{sha1(z.read(i))}  {name}/{i.filename}")
    with open(rom, "rb") as f:
        lines.append(f"{sha1(f.read())}  {name}")
    sums = os.path.join(dst_dir, "SHA1SUMS.txt")
    old = []
    if os.path.exists(sums):
        with open(sums, encoding="utf-8") as f:
            old = f.read().splitlines()
    keep = [x for x in old if x.split("  ", 1)[1].split("/")[0] != name]  # replace this ROM's lines
    with open(sums, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(keep + lines, key=lambda x: x.split("  ", 1)[1])) + "\n")


def copy_output(src: str, dst: str, fragments: list[str]) -> None:
    os.makedirs(dst, exist_ok=True)
    for name in sorted(os.listdir(src)):
        path = os.path.join(src, name)
        if os.path.isfile(path):
            if name != ".DS_Store":
                shutil.copy2(path, os.path.join(dst, name))
        elif name in fragments:
            print(f"  skip {name}/ (fragments)")
        elif name == "music":
            shutil.copytree(path, os.path.join(dst, name), dirs_exist_ok=True)
        elif name == "portrait-sheet":
            os.makedirs(os.path.join(dst, "sheets"), exist_ok=True)
            for sheet in sorted(os.listdir(path)):
                out = os.path.join(path, sheet, "out")
                for page in sorted(os.listdir(out)) if os.path.isdir(out) else []:
                    shutil.copy2(os.path.join(out, page), os.path.join(dst, "sheets", page))
        elif all(n.lower().endswith(IMAGES) for n in os.listdir(path) if n != ".DS_Store"):
            print(f"  {name}.cbz: {cbz(path, os.path.join(dst, name + '.cbz'))} images")
        else:
            copy_output(path, os.path.join(dst, name), fragments)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("game", choices=sorted(GAMES))
    ap.add_argument("--library", default=os.path.expanduser("~/game-library"))
    args = ap.parse_args()
    cfg = GAMES[args.game]
    src = os.path.join(ROOT, args.game, "output")
    dst = os.path.join(args.library, cfg["id"])
    os.makedirs(dst, exist_ok=True)
    copy_output(src, dst, cfg["fragments"])
    captures = os.path.join(ROOT, args.game, "captures")
    if os.path.isdir(captures):
        shutil.copytree(captures, os.path.join(dst, "captures"), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".DS_Store"))
    for rom in cfg["roms"]:
        archive_rom(os.path.join(ROOT, "roms", rom), os.path.join(args.library, "_original", PLATFORM))
    print(f"{args.game} -> {dst}")
    for need in [os.path.join(dst, "README.md"), os.path.join(args.library, cfg["id"].split("/")[0] + ".md")]:
        if not os.path.exists(need):
            print(f"  write by hand: {need}")


if __name__ == "__main__":
    main()
