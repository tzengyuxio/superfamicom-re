"""portrait-sheet/1 manifest of the officers' faces (needs export.py's output first).

Usage: .venv/bin/python tenbu/sheet_manifest.py
then:  .venv/bin/python -I ~/.claude/skills/portrait-sheet/render.py tenbu/output/portrait-sheet/<set>/sheet.json \
           tenbu/output/portrait-sheet/<set>/out   (set: tenbu, tenbu-shared)

The 4 scenarios' person records (output/scenario_persons.csv) point at 248 of the 250 faces (output/faces/NNN.png,
32x40; 71 and 135 are unused). One cell per person (name + face: the generic faces are dealt out again in each
scenario, so a generic officer can look different in another scenario), in the game's order: scenario 190's person
records, then the persons each later scenario adds. The reading is the `sub`. Persons whose face is used by at most
2 persons make the set tenbu (武將頭像, tagged 專屬 / 共用N人; the 2 faces no one uses close it, unnamed and
unseen); those on the generic faces, each shared by 4-12
persons, make tenbu-shared (共用頭像, no tags since every face is shared).
"""
import csv
import json
import os
import shutil
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SLUG = "tenbu"
FACES = 250
SHARED = 2  # faces of more persons than this are the generic faces, in their own set tenbu-shared


def main() -> None:
    src = os.path.join(HERE, "output")
    with open(os.path.join(src, "scenario_persons.csv"), encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    persons: dict[tuple[str, int], str] = {}  # (name, face) -> reading, in first-appearance order
    for r in rows:
        key = (r["名前"].replace("　", ""), int(r["顔"]))
        persons.setdefault(key, unicodedata.normalize("NFKC", r["読み"]).strip())
    users: dict[int, int] = {}
    for _, face in persons:
        users[face] = users.get(face, 0) + 1
    for slug, title, own in ((SLUG, "武將頭像", True), (f"{SLUG}-shared", "共用頭像", False)):
        out = os.path.join(src, "portrait-sheet", slug)
        os.makedirs(os.path.join(out, "faces"), exist_ok=True)
        chars = []
        for (name, n), sub in persons.items():
            if (users[n] <= SHARED) != own:
                continue
            face = f"faces/{n:03d}.png"
            shutil.copy(os.path.join(src, face), os.path.join(out, face))
            ch = {"face": face, "name": name, "sub": sub}
            if own:
                ch["tags"] = ["專屬"] if users[n] == 1 else [{"text": f"共用{users[n]}人", "style": "quiet"}]
            chars.append(ch)
        if own:
            for n in sorted(set(range(FACES)) - set(users)):
                face = f"faces/{n:03d}.png"
                shutil.copy(os.path.join(src, face), os.path.join(out, face))
                chars.append({"face": face, "unseen": True, "tags": [{"text": "無人用", "style": "quiet"}]})
        manifest = {"format": "portrait-sheet/1", "slug": slug, "game": "三國志正史 天舞Spirits",
                    "original": "三国志正史 天舞スピリッツ", "title_font": "lanyang-semibold", "title": title,
                    "platform": "WOLF TEAM　SFC", "theme": {"base": "paper", "name_font": "sourcehan-serif"}, "characters": chars}
        with open(os.path.join(out, "sheet.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"{slug}: {len(chars)} cells, {len({c['face'] for c in chars})} faces -> {out}")


if __name__ == "__main__":
    main()
