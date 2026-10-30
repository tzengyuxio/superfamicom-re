"""portrait-sheet/1 manifest of the officers' faces (needs export.py's output first).

Usage: .venv/bin/python tenbu/sheet_manifest.py
then:  .venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py tenbu/output/portrait-sheet/<set>/sheet.json \
           tenbu/output/portrait-sheet/<set>/out   (set: tenbu, tenbu-shared)

The 4 scenarios' person records (output/scenario_persons.csv) point at 248 of the 250 faces (output/faces/NNN.png,
32x40; 71 and 135 are unused). One cell per face in face order, with every person who uses it as `names`
(full-width padding removed); a face with one person gets the reading as `sub`. Faces of 1-2 persons make the set
tenbu (武將頭像); the generic faces, each shared by 4-12 persons, make tenbu-shared (共用頭像).
"""
import csv
import json
import os
import shutil
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "tenbu"
SHARED = 2  # faces of more persons than this are the generic faces, in their own set tenbu-shared


def main() -> None:
    src = os.path.join(HERE, "output")
    with open(os.path.join(src, "scenario_persons.csv"), encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    faces: dict[int, dict] = {}
    for r in rows:
        name = r["名前"].replace("　", "")
        cell = faces.setdefault(int(r["顔"]), {"names": [], "subs": []})
        if name not in cell["names"]:
            cell["names"].append(name)
            cell["subs"].append(unicodedata.normalize("NFKC", r["読み"]).strip())
    for slug, title, own in ((SLUG, "武將頭像", True), (f"{SLUG}-shared", "共用頭像", False)):
        out = os.path.join(src, "portrait-sheet", slug)
        os.makedirs(os.path.join(out, "faces"), exist_ok=True)
        chars = []
        for n, cell in sorted(faces.items()):
            if (len(cell["names"]) <= SHARED) != own:
                continue
            face = f"faces/{n:03d}.png"
            shutil.copy(os.path.join(src, face), os.path.join(out, face))
            ch = {"face": face, "names": cell["names"]}
            if len(cell["names"]) == 1:
                ch["sub"] = cell["subs"][0]
            chars.append(ch)
        manifest = {"format": "portrait-sheet/1", "slug": slug, "game": "三國志正史 天舞Spirits",
                    "original": "三国志正史 天舞スピリッツ", "title_font": "lanyang-semibold", "title": title,
                    "platform": "WOLF TEAM　SFC", "theme": {"base": "paper", "name_font": "sourcehan-serif"}, "characters": chars}
        with open(os.path.join(out, "sheet.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"{slug}: {len(chars)} faces -> {out}")


if __name__ == "__main__":
    main()
