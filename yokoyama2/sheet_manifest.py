"""portrait-sheet/1 manifest of the officers' faces (needs export.py's output first).

Usage: .venv/bin/python yokoyama2/sheet_manifest.py
then:  .venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py yokoyama2/output/portrait-sheet/yokoyama2/sheet.json \
           yokoyama2/output/portrait-sheet/yokoyama2/out

The 229 persons each have their own face (output/faces/NNN_名前.png, 48x64); all of them appear in at least one
scenario.
Cells follow the name table (gojūon order), with the reading as `sub`.
"""
import csv
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "yokoyama2"
PLACEMENTS = ["189配置", "200配置", "215配置"]


def main() -> None:
    src = os.path.join(HERE, "output")
    out = os.path.join(src, "portrait-sheet", SLUG)
    os.makedirs(os.path.join(out, "faces"), exist_ok=True)
    with open(os.path.join(src, "persons.csv"), encoding="utf-8-sig") as f:
        persons = list(csv.DictReader(f))
    files = {f[:3]: f for f in os.listdir(os.path.join(src, "faces")) if f.endswith(".png")}
    chars = []
    for p in persons:
        if all(p[c] == "不在" for c in PLACEMENTS):
            continue
        face = f"faces/{int(p['Id']):03d}.png"
        shutil.copy(os.path.join(src, "faces", files[f"{int(p['Id']):03d}"]), os.path.join(out, face))
        chars.append({"face": face, "name": p["名前"], "sub": p["読み"]})
    manifest = {"format": "portrait-sheet/1", "slug": SLUG, "game": "橫山光輝三國志2", "original": "横山光輝 三国志2",
                "title_font": "lanyang-semibold", "title": "武將頭像", "platform": "ANGEL　1993　SFC",
                "theme": {"base": "paper", "name_font": "sourcehan-serif"}, "characters": chars}
    with open(os.path.join(out, "sheet.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"{len(chars)} faces ({len(persons)} persons) -> {out}")


if __name__ == "__main__":
    main()
