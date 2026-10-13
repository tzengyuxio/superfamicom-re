"""SFC スーパー蒼き狼と白き牝鹿・元朝秘史 (KOEI, 1993) ROM decoding.

Offsets are file offsets of the headerless 1.5 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
The LZ decompressor ($C0:9DB4) is the shared one in tools/koei_lz.py. Most tables are the FC version's
(famicom-re/genchou) with a few changes; field meanings follow the FC documentation unless noted.
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Super Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")
LZ_TABLES = 0x9C57                       # decompressor table block, routine at $C0:9DB4
LZ_POINTERS = 0x8A9DA                    # 352 long pointers ($C8:A9DA, read by $C6:7EC9)
LZ_COUNT = 352

# Text: half-width kana (ESC H = hiragana, the default; ESC K = katakana), ASCII, and 2-byte codes 0x8140 + g
# for font glyph g (data/charset.txt). Font: 16x16 1bpp, 32 bytes, four 8x8 tiles TL TR BL BR ($C7:5C79).
TEXT_BASE = 0x8140
GLYPH_COUNT = 2046                       # codes 0x8140-0x893D
FONT_SPLIT = 0x400                       # glyphs below at file 32 g ($C0), the rest at 0x130000 + 32 g ($D3)
FONT_HIGH = 0x130000

# Scenarios: 4 (the 4th, "世界帝国への道", is not in the menu). Starting one copies ($C4:400F):
#   block A ($C4:DB80, 3-byte pointers) -> WRAM $7E:37F7, 0x149D bytes: 1 byte, persons, countries, houses
#   block B ($C4:DB8C)                  -> $7E:4F38, 0x524 bytes: women, ..., start year
#   FAMILY ($C9:5300)                   -> $7E:4C94, 0x2A4 bytes (same for every scenario)
#   REGION_NAMES[mongol or world]       -> $7E:2000, 0x210 bytes; REGION_POS[...] -> $7E:545C, 0x42 bytes
SCENARIO_COUNT = 4
SCENARIO_MENU = 0x4D7FE                  # 4 long pointers to "1 モンゴル高原の統一" ...
SCENARIO_A = 0x4DB80
SCENARIO_B = 0x4DB8C
A_SIZE, B_SIZE = 0x149D, 0x524
A_WRAM, B_WRAM = 0x37F7, 0x4F38
PERSONS_AT, PERSON_SIZE, PERSON_SLOTS = 1, 26, 109
COUNTRIES_AT, COUNTRY_SIZE, COUNTRY_SLOTS = 0xB13, 50, 33
HOUSES_AT, HOUSE_SIZE, HOUSE_SLOTS = 0x1185, 24, 33
WOMEN_AT, WOMAN_SIZE, WOMAN_SLOTS = 0, 21, 32
YEAR_AT = 0x51F                          # in block B, LE16
# After copying scenario 4 the loader empties person slot 69 (耶律楚材, age -5) by setting +23 = 80 ($C4:40E1)
LOADER_EMPTIES = {3: [69]}
FAMILY = 0x95300                         # 26 person-format slots: 0-6 the player's family in scenario 1
FAMILY_SLOTS = [0, 1, 2, 3, 4, 5, 6, 13]
MONGOL_COUNTRIES = 14                    # scenario 1 uses the 14 Mongol regions, the others 33 countries
REGION_NAMES = {"mongol": 0x69037, "world": 0x69247}   # 33 x 16 bytes each
REGION_POS = {"mongol": 0x68FB3, "world": 0x68FF5}     # 33 x bytes, then 33 y bytes (label position on the map)

# Master tables (bank $C7 unless noted)
UNITS = 0x2E1B0                          # 16 x 8 bytes (same as FC bank 4 $9B2C)
UNIT_COUNT = 16
UNIT_NAMES = 0x7D264                     # 16 long pointers
UNIT_PRICES = 0x7D0FD                    # 16 bytes: conscription price / 100
UNIT_COM_ORDER = 0x7D10D                 # 16 unit ids: the order the computer fills its armies
TRADE_TABLE = 0x7D0CD                    # 4 merchants x 12 goods (meaning not confirmed)
GOODS_NAMES = 0x7D1FA                    # 12 long pointers
GOODS_COUNT = 12
MERCHANT_NAMES = 0x7D3D1                 # 4 long pointers
POST_NAMES = 0x7D11D                     # 4 long pointers: 将軍 政治顧問 領主 国王
CULTURE_NAMES = 0x7D159                  # 8 long pointers: モンゴル 内アジア インド 日本 西欧 東欧 イスラム 中国
GRADES = "EDCBA"                         # ability values 0-4
UNIT_CLASSES = ["歩兵", "特殊", "騎兵"]

# Faces: 40x48 = 5x6 4bpp tiles row-major (960 bytes). Face code bit 15 clear: portrait, LZ entry
# PORTRAIT_ENTRY + n ($C4:5E31); persons use n = code (0-56), women n = WOMAN_PORTRAIT + code. Bit 15 set:
# composed face ($C4:5CEC / $C4:5812), see Rom.face_tiles. Portraits use CGRAM palette 3, composed faces
# palette 2 for face groups 4-6 (code bits 12-14) and 3 otherwise; ROM copies of the two in FACE_PALETTES.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_ENTRY = 38
PORTRAIT_COUNT = 97
WOMAN_PORTRAIT = 57
FACE_PALETTES = {2: 0x140B7, 3: 0x140D7}  # 16 colours each; loaded with the other BG palettes at boot
HEAD_LAYOUT = 0x4DBED                    # 56 x LE16: layout of head h = culture * 7 + n
PART_SIZE = 0x4DC5D                      # layout x 5 x LE16 (eyes, nose, mouth: width * 10 + rows; top, body: tiles)
PART_POS = 0x4DD39                       # layout x 5 x LE16: column * 10 + row of the part's origin
TOP_RUNS = 0x4DE15                       # layout x 4 x LE16: count, then runs (col, row, width, rows as 4 digits)
BODY_RUNS = 0x4DEC5                      # layout x 5 x LE16: count, then runs
PART_TILE = 0x4DFAD                      # layout x 5 x LE16: first tile of the part (variant 0) in the head
HEAD_DATA = [0x140000, 0x150000]         # heads 0-27 / 28-55, 0x780 bytes (60 tiles) each, uncompressed
PART_BITS = [6, 5, 4, 8, 7]              # face code bit choosing variant 1 of eyes, nose, mouth, top, body
PART_NAMES = ["eyes", "nose", "mouth", "top", "body"]
# Face group (code bits 12-14) -> culture, inferred from the persons' culture field (+22) of the composed faces
# (group 0: 51/51 モンゴル, 1: 28/28 中国, ..., 4: 3/4 日本); not the culture numbering of the person record.
FACE_GROUPS = ["モンゴル", "中国", "内アジア", "インド", "日本", "西欧", "東欧", "イスラム"]

# Main map: one 184x192 picture, 23x24 4bpp tiles row-major (LZ entry 3 Mongolia for scenario 1, 4 the world
# for the others), shown on BG2 (tiles 0x70 + 23 row + column, palette 6). Colour 15 is the inside of the regions,
# which the game paints in its own colours and patterns per house; REGION_POS gives the label position of each
# region in map pixels.
MAP_ENTRY = {"mongol": 3, "world": 4}
MAP_W, MAP_H = 23, 24
MAP_PALETTE = {"mongol": 0x8B49A, "world": 0x8B51A}   # 16 colours each, CGRAM palette 6 on the main screen
MAP_FILL = 15

# Palette block $C8:ADFA: 16-colour palettes, palette p at PALETTE_BLOCK + 32 p (MAP_PALETTE are p 0x35 / 0x39).
PALETTE_BLOCK = 0x8ADFA

# Battle maps: 47 records of 868 bytes, LZ entries BATTLE_ENTRY + n (n = Mongol region 0-13, then 14 + world
# country 0-32; $C7:92EB), byte-identical to the FC version's: 28x21 tile numbers, 14x10 entry cells, 14x10
# terrain. Drawn on BG2 at tile (2, 3) as tile 0x40 + v, palette 6. Tiles: LZ entry BATTLE_TILESET_ENTRY + k
# (tile v at 32 v), palette BATTLE_PALETTE0 + 2k of the palette block (the next one differs only in colours 13-14,
# presumably the water animation); k = 0 in Mongolia, else the byte of BATTLE_TILESET_OF for the country.
BATTLE_ENTRY = 136
BATTLE_COUNT = 47
BATTLE_TILE_W, BATTLE_TILE_H = 28, 21
BATTLE_W, BATTLE_H = 14, 10
BATTLE_NO_ENTRY = 0x30
BATTLE_TILESET_ENTRY = 229               # 229-233 ($C7:9400: 0xE5 + k)
BATTLE_TILESETS = 5
BATTLE_TILESET_OF = 0x7D807              # 33 bytes, world country -> tile set 0-4
BATTLE_PALETTE0 = 0x20                   # $C7:9518: palette 0x20 + 2k
TERRAIN_NAMES = {0: "平地", 1: "城", 2: "街", 3: "砂漠", 4: "森林", 5: "山岳", 6: "河川", 7: "湖・海"}


def hirom(addr: int) -> int:
    return addr & 0x3FFFFF


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


def decode_tile(raw: bytes) -> list[int]:
    """One 4bpp SNES tile (32 bytes) -> 64 colour numbers, row-major."""
    out = []
    for y in range(8):
        p0, p1, p2, p3 = raw[2 * y], raw[2 * y + 1], raw[16 + 2 * y], raw[17 + 2 * y]
        for x in range(7, -1, -1):
            out.append((p0 >> x & 1) | (p1 >> x & 1) << 1 | (p2 >> x & 1) << 2 | (p3 >> x & 1) << 3)
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    """SNES colour -> 8-bit RGB (5-bit value << 3 | value >> 2, as Mesen shows it)."""
    return tuple((c >> s & 31) << 3 | (c >> s & 31) >> 2 for s in (0, 5, 10))


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]


def load_charset(path: str = CHARSET) -> str:
    with open(path, encoding="utf-8") as f:
        cs = "".join(line.rstrip("\n") for line in f if not line.startswith("#"))
    assert len(cs) == GLYPH_COUNT, len(cs)
    return cs


def signed(b: int) -> int:
    return b - 256 if b >= 128 else b


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        assert koei_lz.find_tables(self.data) == LZ_TABLES
        self.charset = load_charset()
        self._cache: dict[int, bytes] = {}

    # --- generic ---
    def ptr(self, at: int) -> int:
        """File offset of the long pointer at `at`."""
        return hirom(int.from_bytes(self.data[at:at + 3], "little"))

    def entry(self, n: int) -> bytes:
        """Decompressed LZ entry n of the main pointer table."""
        if n not in self._cache:
            self._cache[n] = koei_lz.decompress(self.data, self.ptr(LZ_POINTERS + 3 * n), LZ_TABLES)[0]
        return self._cache[n]

    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g."""
        a = 32 * g if g < FONT_SPLIT else FONT_HIGH + 32 * g
        raw = self.data[a:a + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    def text(self, raw: bytes) -> str:
        """Game text -> str: 2-byte codes through the charset; half-width kana as hiragana (ESC H, default)
        or katakana (ESC K); '-' in katakana is ー; other bytes as cp932; 0A newline; NUL ends."""
        out, run, kata = [], bytearray(), False

        def flush() -> None:
            if run:
                s = unicodedata.normalize("NFKC", run.decode("cp932", "replace"))
                if kata:
                    s = s.replace("-", "ー")
                else:
                    s = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)
                out.append(s)
                run.clear()

        i = 0
        while i < len(raw) and raw[i]:
            b = raw[i]
            if b == 0x1B and i + 1 < len(raw):
                flush()
                if raw[i + 1] in b"KH":
                    kata = raw[i + 1] == ord("K")
                i += 2
            elif 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
                flush()
                c = (b << 8 | raw[i + 1]) - TEXT_BASE
                out.append(self.charset[c] if 0 <= c < GLYPH_COUNT else f"{{{b:02X}{raw[i + 1]:02X}}}")
                i += 2
            else:
                run.append(b)
                i += 1
        flush()
        return "".join(out)

    def string(self, at: int, limit: int = 64) -> str:
        return self.text(self.data[at:at + limit])

    def strings(self, table: int, count: int) -> list[str]:
        return [self.string(self.ptr(table + 3 * k)) for k in range(count)]

    # --- master tables ---
    def scenario_titles(self) -> list[str]:
        """'モンゴル高原の統一' ... (the menu line without its number)."""
        return [t.split(" ", 1)[1] for t in self.strings(SCENARIO_MENU, SCENARIO_COUNT)]

    def region_names(self, world: bool) -> list[str]:
        base = REGION_NAMES["world" if world else "mongol"]
        n = COUNTRY_SLOTS if world else MONGOL_COUNTRIES
        return [self.string(base + 16 * k, 16) for k in range(n)]

    def region_positions(self, world: bool) -> list[tuple[int, int]]:
        base = REGION_POS["world" if world else "mongol"]
        n = COUNTRY_SLOTS if world else MONGOL_COUNTRIES
        return [(self.data[base + k], self.data[base + COUNTRY_SLOTS + k]) for k in range(n)]

    def culture_names(self) -> list[str]:
        return self.strings(CULTURE_NAMES, 8)

    def post_names(self) -> list[str]:
        return self.strings(POST_NAMES, 4)

    def units(self) -> list[dict]:
        """16 units: +0 class (0 歩兵 1 特殊 2 騎兵), +1 戦意, +2 機動, +3 近接, +4 突撃, +5 矢弾 (5 = none),
        +6 防御 (0-4 = E-A), +7 special (FF none); price = conscription price; order = computer priority."""
        names = self.strings(UNIT_NAMES, UNIT_COUNT)
        order = list(self.data[UNIT_COM_ORDER:UNIT_COM_ORDER + UNIT_COUNT])
        out = []
        for u in range(UNIT_COUNT):
            r = self.data[UNITS + 8 * u:UNITS + 8 * u + 8]
            out.append({"id": u, "name": names[u], "class": r[0], "morale": r[1], "mobility": r[2], "melee": r[3],
                        "charge": r[4], "missile": r[5], "defense": r[6], "special": r[7],
                        "price": self.data[UNIT_PRICES + u] * 100, "com_rank": order.index(u) + 1})
        return out

    def goods_names(self) -> list[str]:
        return self.strings(GOODS_NAMES, GOODS_COUNT)

    def merchant_names(self) -> list[str]:
        return self.strings(MERCHANT_NAMES, 4)

    def trade_table(self) -> list[list[int]]:
        return [list(self.data[TRADE_TABLE + GOODS_COUNT * m:TRADE_TABLE + GOODS_COUNT * (m + 1)]) for m in range(4)]

    # --- scenarios ---
    def block_a(self, sc: int) -> bytes:
        p = self.ptr(SCENARIO_A + 3 * sc)
        return self.data[p:p + A_SIZE]

    def loaded_a(self, sc: int) -> bytes:
        """Block A as the loader leaves it in WRAM (LOADER_EMPTIES applied)."""
        a = bytearray(self.block_a(sc))
        for k in LOADER_EMPTIES.get(sc, []):
            a[PERSONS_AT + PERSON_SIZE * k + 23] = 0x80
        return bytes(a)

    def block_b(self, sc: int) -> bytes:
        p = self.ptr(SCENARIO_B + 3 * sc)
        return self.data[p:p + B_SIZE]

    def year(self, sc: int) -> int:
        return le16(self.block_b(sc), YEAR_AT)

    def country_count(self, sc: int) -> int:
        return MONGOL_COUNTRIES if sc == 0 else COUNTRY_SLOTS

    def person(self, r: bytes, slot: int) -> dict:
        """26 bytes: +0 name (16), +16 house (FF none), +17 country, +18 体力 (high nibble current, low nibble
        max: the card shows "hi/lo"), +19 戦闘 (shown as 戦力) / 政治, +20 魅力 / 指揮 (nibbles, 0-4 = E-A),
        +21 age (signed), +22 bits 2-4 culture (inferred; others unknown), +23 status (3 国王, 2 inferred 領主,
        1 家臣, 0 在野; 80 empty slot), +24 face code LE16."""
        return {"slot": slot, "raw": r, "name": self.text(r[:16]), "house": r[16], "country": r[17],
                "hp": r[18] >> 4, "hp_max": r[18] & 15, "戦闘": r[19] >> 4, "政治": r[19] & 15,
                "魅力": r[20] >> 4, "指揮": r[20] & 15, "age": signed(r[21]), "culture": r[22] >> 2 & 7,
                "unknown22": r[22] & 0xE3, "status": r[23], "face": le16(r, 24)}

    def persons(self, sc: int) -> list[dict]:
        """Occupied slots of the scenario's 109 person slots (as loaded, see LOADER_EMPTIES)."""
        a = self.loaded_a(sc)
        out = []
        for k in range(PERSON_SLOTS):
            o = PERSONS_AT + PERSON_SIZE * k
            p = self.person(a[o:o + PERSON_SIZE], k)
            if p["status"] != 0x80 and p["name"]:
                out.append(p)
        return out

    def family(self) -> list[dict]:
        """The 26-byte person-format slots of FAMILY that hold a person (scenario 1's family and タイチャル)."""
        out = []
        for k in FAMILY_SLOTS:
            o = FAMILY + PERSON_SIZE * k
            out.append(self.person(self.data[o:o + PERSON_SIZE], k))
        return out

    def countries(self, sc: int) -> list[dict]:
        """50 bytes: +0 next country of the same house (WRAM pointer, 3 bytes; 0 = end), +3 country id,
        +4..8 neighbours (FF = none), +9 金 +11 食糧 +13 人口 (LE16), +15..18 住民配分 % (農業 牧畜 特産 街),
        +19..22 unknown, +23..38 units per unit type (FC: inferred), +39 +40 unknown, +41 flag, +42 +43 unknown,
        +44..47 住民配分 (target?), +48 +49 unknown. +9..+49 = FC's country record +1..+41 (FC +0, the owner, is
        replaced by the house chain: see houses())."""
        a = self.block_a(sc)
        out = []
        for c in range(self.country_count(sc)):
            o = COUNTRIES_AT + COUNTRY_SIZE * c
            r = a[o:o + COUNTRY_SIZE]
            nxt = le16(r, 0)
            out.append({"id": c, "raw": r, "next": (nxt - (A_WRAM + COUNTRIES_AT)) // COUNTRY_SIZE if nxt else None,
                        "neighbours": [n for n in r[4:9] if n != 0xFF], "gold": le16(r, 9),
                        "food": le16(r, 11), "population": le16(r, 13), "split": list(r[15:19]),
                        "unknown19": list(r[19:23]), "units": list(r[23:39]), "unknown39": [r[39], r[40]],
                        "flag": r[41], "unknown42": [r[42], r[43]], "split2": list(r[44:48]),
                        "unknown48": [r[48], r[49]]})
        return out

    def houses(self, sc: int) -> list[dict]:
        """24 bytes: +0 name (16, the last byte 0), +17 first country (3-byte WRAM pointer; the next country of
        the house is at country +0), +20 ruler (3-byte WRAM pointer to a person slot), +23 unknown. Only slots
        with a name."""
        a = self.block_a(sc)
        countries = self.countries(sc)
        out = []
        for h in range(HOUSE_SLOTS):
            o = HOUSES_AT + HOUSE_SIZE * h
            r = a[o:o + HOUSE_SIZE]
            name = self.text(r[:16])
            if not name:
                continue
            first, ruler = le16(r, 17), le16(r, 20)
            chain = []
            c = (first - (A_WRAM + COUNTRIES_AT)) // COUNTRY_SIZE if first else None
            while c is not None and 0 <= c < len(countries) and c not in chain:
                chain.append(c)
                c = countries[c]["next"]
            out.append({"id": h, "raw": r, "name": name, "countries": chain,
                        "ruler": (ruler - (A_WRAM + PERSONS_AT)) // PERSON_SIZE if ruler else None,
                        "unknown23": r[23]})
        return out

    def women(self, sc: int) -> list[dict]:
        """21 bytes: +0 name (15), +15 unknown (FF), +16 +17 unknown, +18 country, +19 face code LE16
        (bit 15 clear: portrait WOMAN_PORTRAIT + code)."""
        b = self.block_b(sc)
        out = []
        for k in range(WOMAN_SLOTS):
            r = b[WOMAN_SIZE * k:WOMAN_SIZE * (k + 1)]
            name = self.text(r[:15])
            if not name:
                break
            out.append({"slot": k, "raw": r, "name": name, "unknown15": r[15], "unknown16": r[16],
                        "unknown17": r[17], "country": r[18], "face": le16(r, 19)})
        return out

    # --- faces ---
    def portrait_tiles(self, n: int) -> bytes:
        return self.entry(PORTRAIT_ENTRY + n)[:FACE_BYTES]

    @staticmethod
    def face_fields(code: int) -> dict:
        """Composed face code: bits 12-14 face group (FACE_GROUPS), 9-11 head in the group (mod 7), PART_BITS."""
        culture, n = code >> 12 & 7, (code >> 9 & 7) % 7
        return {"culture": culture, "head": culture * 7 + n,
                "variants": [code >> b & 1 for b in PART_BITS]}

    def face_palette_number(self, code: int, woman: bool = False) -> int:
        if not code & 0x8000:
            return 3
        return 2 if self.face_fields(code)["culture"] in (4, 5, 6) else 3

    def face_palette(self, code: int) -> list[int]:
        n = self.face_palette_number(code)
        return [le16(self.data, FACE_PALETTES[n] + 2 * i) for i in range(16)]

    def head_parts(self, head: int) -> list[dict]:
        """Per part (eyes, nose, mouth, top, body): tiles (list of face cell numbers 0-29 in source order) and
        the source tile offset of variant 0 in the head's 60 tiles (variant 1 follows)."""
        layout = le16(self.data, HEAD_LAYOUT + 2 * head)
        out = []
        for k in range(5):
            size = le16(self.data, PART_SIZE + 10 * layout + 2 * k)
            pos = le16(self.data, PART_POS + 10 * layout + 2 * k)
            col0, row0 = pos // 10, pos % 10
            cells = []
            if k < 3:
                w, rows = size // 10, size % 10
                count = w * rows
                for r in range(rows):  # $C4:5ADF copies every row from the same source (rows is always 1)
                    cells += [(row0 + r) * FACE_W + col0 + x for x in range(w)]
            else:
                count = size
                runs = TOP_RUNS + 8 * layout if k == 3 else BODY_RUNS + 10 * layout
                for j in range(1, le16(self.data, runs) + 1):
                    run = le16(self.data, runs + 2 * j)
                    dc, dr, w, rows = run // 1000, run // 100 % 10, run // 10 % 10, run % 10
                    for r in range(rows):
                        cells += [(row0 + dr + r) * FACE_W + col0 + dc + x for x in range(w)]
            out.append({"cells": cells, "count": count,
                        "tile": le16(self.data, PART_TILE + 10 * layout + 2 * k)})
        return out

    def head_tiles(self, head: int) -> bytes:
        """The head's 60 source tiles (both variants of every part)."""
        base = HEAD_DATA[head // 28] + (head % 28) * 0x780
        return self.data[base:base + 0x780]

    def face_tiles(self, code: int, woman: bool = False) -> bytes:
        """960 bytes of 4bpp tiles of a face code, as $C4:5E31 (portrait) or $C4:5812 (composed) builds them."""
        if not code & 0x8000:
            return self.portrait_tiles(code + (WOMAN_PORTRAIT if woman else 0))
        f = self.face_fields(code)
        src = self.head_tiles(f["head"])
        out = bytearray(FACE_BYTES)
        for part, v in zip(self.head_parts(f["head"]), f["variants"]):
            t0 = part["tile"] + v * part["count"]
            if len(part["cells"]) == part["count"]:
                for i, cell in enumerate(part["cells"]):
                    out[32 * cell:32 * cell + 32] = src[32 * (t0 + i):32 * (t0 + i) + 32]
        return bytes(out)

    def face_pixels(self, code: int, woman: bool = False) -> list[int]:
        """40x48 colour numbers of a face code, row-major."""
        tiles = self.face_tiles(code, woman)
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, code: int, woman: bool = False) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette(code)]
        return [pal[v] for v in self.face_pixels(code, woman)]

    # --- main map ---
    def map_tiles(self, world: bool) -> bytes:
        return self.entry(MAP_ENTRY["world" if world else "mongol"])

    def map_pixels(self, world: bool) -> list[int]:
        """184x192 colour numbers, row-major."""
        tiles = self.map_tiles(world)
        w = MAP_W * 8
        out = [0] * (w * MAP_H * 8)
        for t in range(MAP_W * MAP_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // MAP_W * 8 + i // 8) * w + t % MAP_W * 8 + i % 8] = v
        return out

    def map_palette(self, world: bool) -> list[int]:
        base = MAP_PALETTE["world" if world else "mongol"]
        return [le16(self.data, base + 2 * i) for i in range(16)]

    def map_rgb(self, world: bool) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.map_palette(world)]
        return [pal[v] for v in self.map_pixels(world)]

    # --- battle maps ---
    def battle_record(self, n: int) -> bytes:
        return self.entry(BATTLE_ENTRY + n)

    def battle_values(self, n: int) -> list[int]:
        """28x21 tile numbers (row-major) of the drawn map: tile v of the battle tile set."""
        return list(self.battle_record(n)[:BATTLE_TILE_W * BATTLE_TILE_H])

    def battle_entries(self, n: int) -> list[int | None]:
        """14x10 entry cells: neighbouring country index, None = no entry (record offset 0x24C)."""
        o = BATTLE_TILE_W * BATTLE_TILE_H
        return [None if v == BATTLE_NO_ENTRY else v for v in self.battle_record(n)[o:o + BATTLE_W * BATTLE_H]]

    def battle_terrain(self, n: int) -> list[int]:
        """14x10 terrain per cell, row-major (record offset 0x2D8; TERRAIN_NAMES)."""
        o = BATTLE_TILE_W * BATTLE_TILE_H + BATTLE_W * BATTLE_H
        return list(self.battle_record(n)[o:o + BATTLE_W * BATTLE_H])

    def battle_tileset(self, n: int) -> int:
        """0-4: Mongol maps use 0, world country c uses the byte at BATTLE_TILESET_OF + c ($C7:D807)."""
        return 0 if n < MONGOL_COUNTRIES else self.data[BATTLE_TILESET_OF + n - MONGOL_COUNTRIES]

    def battle_palette(self, tileset: int) -> list[int]:
        base = PALETTE_BLOCK + 32 * (BATTLE_PALETTE0 + 2 * tileset)
        return [le16(self.data, base + 2 * i) for i in range(16)]

    def battle_pixels(self, n: int) -> list[int]:
        """224x168 colour numbers, row-major."""
        tiles = self.entry(BATTLE_TILESET_ENTRY + self.battle_tileset(n))
        w = BATTLE_TILE_W * 8
        out = [0] * (w * BATTLE_TILE_H * 8)
        for t, v in enumerate(self.battle_values(n)):
            for i, c in enumerate(decode_tile(tiles[32 * v:32 * v + 32])):
                out[(t // BATTLE_TILE_W * 8 + i // 8) * w + t % BATTLE_TILE_W * 8 + i % 8] = c
        return out

    def battle_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.battle_palette(self.battle_tileset(n))]
        return [pal[v] for v in self.battle_pixels(n)]
