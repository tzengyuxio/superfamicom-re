"""portrait-sheet/1 manifest of the officers' faces (needs export.py's output first).

Usage: .venv/bin/python yokoyama/sheet_manifest.py
then:  .venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py yokoyama/output/portrait-sheet/yokoyama/sheet.json \
           yokoyama/output/portrait-sheet/yokoyama/out

The 224 persons each have their own face (output/faces/NNN_名前.png, 48x64). 任双 is absent from both scenarios
(placement 不在), so his cell is marked unseen.
Cells follow the name table (gojūon order), with the reading as `sub`.
"""
import csv
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "yokoyama"
PLACEMENTS = ["189配置", "219配置"]


def main() -> None:
    src = os.path.join(HERE, "output")
    out = os.path.join(src, "portrait-sheet", SLUG)
    os.makedirs(os.path.join(out, "faces"), exist_ok=True)
    with open(os.path.join(src, "persons.csv"), encoding="utf-8-sig") as f:
        persons = list(csv.DictReader(f))
    files = {f[:3]: f for f in os.listdir(os.path.join(src, "faces")) if f.endswith(".png")}
    chars = []
    for p in persons:
        face = f"faces/{int(p['Id']):03d}.png"
        shutil.copy(os.path.join(src, "faces", files[f"{int(p['Id']):03d}"]), os.path.join(out, face))
        ch = {"face": face, "name": p["名前"], "sub": p["読み"]}
        if all(p[c] == "不在" for c in PLACEMENTS):
            ch["unseen"] = True
        chars.append(ch)
    manifest = {"format": "portrait-sheet/1", "slug": SLUG, "game": "橫山光輝三國志", "original": "横山光輝 三国志",
                "title_font": "lanyang-semibold", "title": "武將頭像", "platform": "ANGEL　1992　SFC",
                "theme": {"base": "ink", "name_font": "sourcehan-serif"}, "characters": chars}
    with open(os.path.join(out, "sheet.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"{len(chars)} faces ({len(persons)} persons) -> {out}")


if __name__ == "__main__":
    main()
