"""SFC 提督の決断II (KOEI, 1993) ROM decoding.

Offsets are file offsets of the headerless 3 MB HiROM image (CPU $C0:0000 = file 0). The program is 65816 code
compiled from C. The LZ decompressor ($C0:F194, tables at 0xF037) is the shared one in tools/koei_lz.py.
The original release and Rev 1 are both supported: Rev 1 moves most code and data (REVISIONS); the scenario
tables are located by parsing the scenario loader itself. See docs/ROM_FORMAT.md.
"""
import os
import re
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Teitoku no Ketsudan II (Japan).zip")
REV1_ROM = os.path.join(REPO, "roms", "Teitoku no Ketsudan II (Japan) (Rev 1).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")
LZ_TABLES = 0xF037
ENTRY_COUNT = 1052

# Per revision (header version byte 0xFFDB). Addresses are file offsets; "code" are CPU addresses used by the
# verify scripts' Lua hooks.
REVISIONS = {
    0: {"entries": 0x1A9C8E, "face_palettes": 0x14DFB6, "type_names": 0x29E57D, "air_types": 0x29E5D3,
        "titles": 0x29E466, "country_abbr": 0x29E523, "weather": 0x29E559, "kyoten": 0x0AF61D, "dates": 0x0ADE05,
        "code": {"vsprintf": 0xD319FA, "glyph": 0xD30E6B, "face": 0xD46DBC}},
    1: {"entries": 0x1AEE82, "face_palettes": 0x01CE1E, "type_names": 0x29E573, "air_types": 0x29E5C9,
        "titles": 0x29E45C, "country_abbr": 0x29E519, "weather": 0x29E54F, "kyoten": 0x09F6BB, "dates": 0x09DEA3,
        "code": {"vsprintf": 0xD719FA, "glyph": 0xD70E6B, "face": 0xC1A08B}},
}
# printf formats the verify scripts hook: (bytes, which occurrence in the ROM); the same in both versions
FORMATS = {
    "confirm": (b"\x1bK\xbc\xc5\xd8\xb5\x1bH%s\n\x1bK\xcc\xdf\xda\xb2\xd4-\x1bH:%s\n", 0),  # シナリオ%s プレイヤ-:%s
    "date": (b"%4d;%2d<%2d,\0", 0),  # 年 月 日 (glyphs ; < ,) on the main screen
}


def hirom(addr: int) -> int:
    """File offset of CPU address $bb:aaaa (banks $C0-$FF)."""
    return addr & 0x3FFFFF


def le16(raw, o: int) -> int:
    return raw[o] | raw[o + 1] << 8


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]


# ---------------------------------------------------------------- text
# Font: glyph g = 16x16 1bpp, 32 bytes at FONT + 32 g (top-left, top-right, bottom-left, bottom-right 8x8 tiles).
# Two-byte code c (lead byte 0x81-0x9F or 0xE0-): c <= 0x8980 draws glyph c - 0x8140; 0x8981-0x913F draw glyph 0;
# c >= 0x9140 stands for 0x8200 + 0x100 (c - 0x9140), the codes whose low byte is 0 ($D3:0DE3). One-byte codes:
# ASCII, and JIS X 0201 kana 0xA1-0xDF drawn as hiragana, or as katakana after ESC K (ESC H switches back).
# ESC C x selects colour x. Name tables carry no ESC: the game wraps them in ESC K ... ESC H when it prints them.
FONT = 0x2B0000
GLYPH_COUNT = 1216


def load_charset(path: str = CHARSET) -> str:
    with open(path, encoding="utf-8") as f:
        cs = "".join(line.rstrip("\n") for line in f if not line.startswith("#"))
    assert len(cs) == GLYPH_COUNT, len(cs)
    return cs


def code_glyph(code: int) -> int:
    """Font glyph drawn for a two-byte code ($D3:0DE3)."""
    if code >= 0x9140:
        code = 0x8200 + ((code - 0x9140) << 8)
    elif code > 0x8980:
        code = 0x8140
    return code - 0x8140


def _kana(c: int, katakana: bool) -> str:
    s = unicodedata.normalize("NFKC", bytes([c]).decode("cp932"))
    if not katakana and "ァ" <= s <= "ヶ":
        s = chr(ord(s) - 0x60)
    return s


# ---------------------------------------------------------------- scenarios
# The loader ($CA:9703 in the original, scenario number on the stack) copies 19 ROM blocks to WRAM bank $7E with
# memcpy ($D0:950F): 17 per scenario (ROM base + scenario * size), 2 shared by all scenarios. It is found by its
# first instructions and parsed (Rom.loader). Two blocks are special: $7E:726E (拠点 owners) is 200 bytes per
# scenario, the index computed as scenario * 100 * 2; $7E:30FC (ships) has one base for scenarios 0-4 and another
# for 5-9. After the copies the loader sets byte +6 of the 70 records at $7E:6710 to 0xFF, which Rom.wram_image
# repeats; what it does afterwards (the 拠点 records, $7E:8312 flags, ...) is not reproduced.
SCENARIO_COUNT = 10
LOADER_SIGNATURE = bytes.fromhex("f47800f47e00f4fa68")  # PEA $0078; PEA $007E; PEA $68FA (first copy)
BLOCK_NAMES = {
    0x68FA: "sides", 0x726E: "kyoten_owners", 0x7336: "bases", 0x6710: "base_aux", 0x54D8: "ship_classes",
    0x64E0: "sub_classes", 0x92C5: "air_groups", 0x30FC: "ships", 0x86EA: "fleets", 0x251D: "countries",
    0x2634: "admirals", 0x2A30: "generals", 0xA1B6: "navy_reserve", 0x2CC4: "aircraft", 0x2C4C: "tanks",
    0xA216: "army_reserve", 0x8312: "marines", 0x842A: "divisions", 0x8DC5: "submarines",
}

# WRAM tables ($7E:xxxx): address, record size, count
SIDES, SIDE_SIZE = 0x68FA, 60
KYOTEN, KYOTEN_SIZE, KYOTEN_COUNT = 0x6972, 23, 100   # built at game start, not by the loader
KYOTEN_OWNERS = 0x726E
BASES, BASE_SIZE, BASE_COUNT = 0x7336, 58, 70
SHIP_CLASSES, SHIP_CLASS_SIZE, SHIP_CLASS_COUNT = 0x54D8, 27, 152
SUB_CLASSES, SUB_CLASS_SIZE, SUB_CLASS_COUNT = 0x64E0, 20, 28
SHIPS, SHIP_SIZE, SHIP_COUNT = 0x30FC, 36, 255
FLEETS, FLEET_SIZE, FLEET_COUNT = 0x86EA, 45, 39
COUNTRIES, COUNTRY_SIZE, COUNTRY_COUNT = 0x251D, 31, 9
ADMIRALS, ADMIRAL_SIZE, ADMIRAL_COUNT = 0x2634, 17, 60
GENERALS, GENERAL_SIZE, GENERAL_COUNT = 0x2A30, 18, 30
NAVY_RESERVE, NAVY_RESERVE_SIZE = 0xA1B6, 48
ARMY_RESERVE, ARMY_RESERVE_SIZE = 0xA216, 31
AIRCRAFT, AIRCRAFT_SIZE, AIRCRAFT_COUNT = 0x2CC4, 18, 60
TANKS, TANK_SIZE, TANK_COUNT = 0x2C4C, 12, 10
SUBMARINES, SUBMARINE_SIZE, SUBMARINE_COUNT = 0x8DC5, 40, 32
MARINES, MARINE_SIZE, MARINE_COUNT = 0x8312, 7, 40
AUX_RUNTIME = (0x6710, 7, 70, 6)  # record base, size, count, byte set to 0xFF by the loader

SIDE_NAMES = ["日本", "連合国"]
COUNTRY_NAMES = ["日本", "アメリカ", "イギリス", "オランダ", "オーストラリア", "ソ連", "中国", "タイ", "ドイツ"]
TERRAIN = ["平地", "町村", "密林", "山岳"]
RESOURCE_LEVELS = ["無", "小", "中", "大"]
FLEET_MISSIONS = {0x04: "奇襲", 0x07: "哨戒", 0x10: "無し"}

# National power record (68FA): diplomatic relation bit masks (bit = country index), tested by $C3:1086 with
# kind 0-3; the 外交情報 screen shows kind 2 as 軍事協定 (Japan) / 軍事同盟 (Allies) and kind 3 as 援助協定.
RELATION_MASKS = {0x13: "relation0", 0x19: "relation1", 0x1F: "alliance", 0x25: "aid"}

# ---------------------------------------------------------------- faces
# Face f (0-103) = LZ entry 753 + f ($D4:6DBC(x, y, f): pointer table $DA:A561 = entry table + 3 * 753), 40x48 =
# 5x6 4bpp tiles, palette $D4:DFB6 or the next 32 bytes ($D4:6D38), loaded to CGRAM row 15.
# Admiral i (0-59: 0-29 Japanese, 30-59 Allied) has face i, general j (0-29: 0-14 Japanese, 15-29 Allied) face
# 60 + j ($C8:07B4 lists of the 人事 screen); faces 90-103 belong to nobody in the tables.
FACE_FIRST_ENTRY, FACE_COUNT, FACE_W, FACE_H = 753, 104, 5, 6
ADMIRAL_FACE0, GENERAL_FACE0 = 0, 60
# Faces 96-101 are shown by $D4:6CD8 / $D4:6D13 for the player's side: 96 + 3 * side (+ random 0-1) and 98 / 101.
OTHER_FACES = {**{f: "其他" for f in range(90, 96)}, **{f: "日本軍官" for f in (96, 97, 98)},
               **{f: "盟軍軍官" for f in (99, 100, 101)}, 102: "剪影", 103: "剪影"}

# ---------------------------------------------------------------- map
# World map: LZ entry 0 = 1bpp bitmap, 80 bytes (640 px) per row, MSB first, 1 = sea; rows 0-359 are the map,
# map coordinates = pixels (the 拠点 X/Y, fleet and submarine positions). The last 45 rows are something else.
MAP_ENTRY, MAP_W, MAP_H = 0, 640, 360


def decode_tile(raw: bytes, o: int = 0) -> list[list[int]]:
    """8x8 SNES 4bpp tile -> rows of colour indices."""
    return [[sum((raw[o + (k >> 1) * 16 + 2 * y + (k & 1)] >> (7 - x) & 1) << k for k in range(4)) for x in range(8)]
            for y in range(8)]


def tiles_pixels(raw: bytes, w: int, h: int) -> list[int]:
    """w x h tiles stored row by row -> (8 w) x (8 h) colour indices."""
    out = [0] * (64 * w * h)
    for t in range(w * h):
        for y, row in enumerate(decode_tile(raw, 32 * t)):
            for x, c in enumerate(row):
                out[((t // w) * 8 + y) * 8 * w + (t % w) * 8 + x] = c
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return ((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31)


def face_alt_palette(f: int) -> bool:
    """$D4:6D38: faces 30-59, 75-93 and 99- except 102 use the second palette (the Allied side)."""
    r = f >= 0x1E
    if r:
        r = f <= 0x3B or f >= 0x4B
    if r:
        r = f <= 0x5D or f >= 0x63
    if r:
        r = f != 0x66
    return r


class Decoders:
    """Record decoders. Each takes a WRAM bank $7E image (Rom.wram_image or a dump), so the verify scripts can
    apply them to the game's memory."""

    def name(self, raw, o: int, n: int) -> str:
        return self.text(bytes(raw[o:o + n]), katakana=True)

    def sides(self, img) -> list[dict]:
        out = []
        for s in range(2):
            b = img[SIDES + SIDE_SIZE * s:SIDES + SIDE_SIZE * (s + 1)]
            d = {"id": s, "side": SIDE_NAMES[s], "gnp": le16(b, 0), "unk_02": b[2], "base_upkeep": le16(b, 3),
                 "tech_intel": b[5], "tech_ships": b[6], "tech_aircraft": b[7], "tech_weapons": b[8],
                 "tech_industry": b[9]}
            for o, k in RELATION_MASKS.items():
                d[k] = [c for c in range(COUNTRY_COUNT) if le16(b, o) >> c & 1]
            d["raw"] = bytes(b).hex()
            out.append(d)
        return out

    def countries(self, img) -> list[dict]:
        out = []
        for i in range(COUNTRY_COUNT):
            b = img[COUNTRIES + COUNTRY_SIZE * i:COUNTRIES + COUNTRY_SIZE * (i + 1)]
            out.append({"id": i, "country": COUNTRY_NAMES[i], "leader": self.name(b, 0, 13), "number": b[13],
                        "title": self.text(bytes(b[14:29])), "allied_friendship": b[29],
                        "japan_friendship": 99 - b[29], "flags": b[30]})
        return out

    def bases(self, img) -> list[dict]:
        out = []
        for i in range(BASE_COUNT):
            b = img[BASES + BASE_SIZE * i:BASES + BASE_SIZE * (i + 1)]
            out.append({
                "id": i, "name": self.name(b, 0, 11), "x": le16(b, 11), "y": le16(b, 13), "owner": b[15],
                "code": bytes(b[17:19]).decode("ascii"),
                "country": b[20], "production": b[22], "production_max": b[23], "unk_24": le16(b, 24),
                "unk_26": le16(b, 26), "unk_28": b[28], "unk_29": b[29], "oil": b[30] & 3, "ore": b[30] >> 2 & 3,
                "unk_30": b[30] >> 4, "slots": [(b[31 + 2 * k], b[32 + 2 * k]) for k in range(8)], "unk_47": b[47],
                "links": [v for v in b[48:56] if v != 0xFF], "raw": bytes(b).hex()})
        return out

    def kyoten(self, img) -> list[dict]:
        """拠点 records ($7E:6972, set up at game start; the static part comes from Rom.kyoten_static)."""
        out = []
        for i in range(KYOTEN_COUNT):
            b = img[KYOTEN + KYOTEN_SIZE * i:KYOTEN + KYOTEN_SIZE * (i + 1)]
            out.append({"id": i, "name": self.name(b, 0, 11), "x": le16(b, 11), "y": le16(b, 13),
                        "owner": le16(b, 15), "terrain": b[17] & 3, "flags": b[17],
                        "links": [v for v in b[18:23] if v != 0xFF]})
        return out

    def kyoten_owners(self, img) -> list[int]:
        return [le16(img, KYOTEN_OWNERS + 2 * i) for i in range(KYOTEN_COUNT)]

    def ship_classes(self, img) -> list[dict]:
        out = []
        for i in range(SHIP_CLASS_COUNT):
            b = img[SHIP_CLASSES + SHIP_CLASS_SIZE * i:SHIP_CLASSES + SHIP_CLASS_SIZE * (i + 1)]
            out.append({"id": i, "name": self.name(b, 0, 12), "picture": b[14], "torpedo": b[15], "speed": b[16],
                        "supplies": b[17], "country": b[18], "type": b[19], "anti_ship": b[20], "anti_air": b[21],
                        "armor": list(b[22:26]), "aircraft": b[26]})
        return out

    def sub_classes(self, img) -> list[dict]:
        out = []
        for i in range(SUB_CLASS_COUNT):
            b = img[SUB_CLASSES + SUB_CLASS_SIZE * i:SUB_CLASSES + SUB_CLASS_SIZE * (i + 1)]
            out.append({"id": i, "name": self.name(b, 0, 12), "picture": b[14], "torpedo": b[15], "speed": b[16],
                        "supplies": b[17], "country": b[18], "armor": b[19]})
        return out

    def ships(self, img) -> list[dict]:
        out = []
        for i in range(SHIP_COUNT):
            b = img[SHIPS + SHIP_SIZE * i:SHIPS + SHIP_SIZE * (i + 1)]
            name, _, reading = self.name(b, 0, 14).partition(" ")
            out.append({"id": i, "name": name, "reading": reading, "class": b[14] if b[14] != 0xFF else -1,
                        "unk_15": b[15], "unk_16": b[16], "speed": b[17], "unk_18": b[18], "skill": b[19],
                        "unk_20": bytes(b[20:28]).hex(), "anti_ship": b[28], "anti_air": b[29],
                        "armor": list(b[30:34]), "unk_34": b[34], "unk_35": b[35]})
        return out

    def fleets(self, img) -> list[dict]:
        out = []
        for i in range(FLEET_COUNT):
            b = img[FLEETS + FLEET_SIZE * i:FLEETS + FLEET_SIZE * (i + 1)]
            out.append({"id": i, "admiral": b[0] if b[0] != 0xFF else -1, "x": le16(b, 1), "y": le16(b, 3),
                        "mission": b[5], "unk_6": b[6], "unk_8": b[8], "target_x": le16(b, 25),
                        "target_y": le16(b, 27), "raw": bytes(b).hex()})
        return out

    def admirals(self, img) -> list[dict]:
        out = []
        for i in range(ADMIRAL_COUNT):
            b = img[ADMIRALS + ADMIRAL_SIZE * i:ADMIRALS + ADMIRAL_SIZE * (i + 1)]
            out.append({"id": i, "name": self.name(b, 0, 14), "side": i // 30, "face": ADMIRAL_FACE0 + i,
                        "unk_14": b[14], "unk_15": b[15], "unk_16": b[16]})
        return out

    def generals(self, img) -> list[dict]:
        out = []
        for i in range(GENERAL_COUNT):
            b = img[GENERALS + GENERAL_SIZE * i:GENERALS + GENERAL_SIZE * (i + 1)]
            out.append({"id": i, "name": self.name(b, 0, 14), "side": int(i >= 15), "face": GENERAL_FACE0 + i,
                        "unk_14": b[14], "unk_15": b[15], "unk_16": b[16], "unk_17": b[17]})
        return out

    def aircraft(self, img) -> list[dict]:
        out = []
        for i in range(AIRCRAFT_COUNT):
            b = img[AIRCRAFT + AIRCRAFT_SIZE * i:AIRCRAFT + AIRCRAFT_SIZE * (i + 1)]
            out.append({"id": i, "name": self.name(b, 0, 14), "country": b[14], "type": b[15],
                        "combat": b[16] & 15, "range": b[16] >> 4, "flags": b[17]})
        return out

    def tanks(self, img) -> list[dict]:
        out = []
        for i in range(TANK_COUNT):
            b = img[TANKS + TANK_SIZE * i:TANKS + TANK_SIZE * (i + 1)]
            out.append({"id": i, "name": self.name(b, 0, 11), "caliber": (b[11] & 3) + 1,
                        "armor": (b[11] >> 2 & 3) + 1, "flags": b[11] >> 4})
        return out

    def navy_reserve(self, img) -> list[dict]:
        out = []
        for s in range(2):
            b = img[NAVY_RESERVE + NAVY_RESERVE_SIZE * s:NAVY_RESERVE + NAVY_RESERVE_SIZE * (s + 1)]
            out.append({"side": s, "budget": le16(b, 0), "materials": le16(b, 2), "marines": b[4],
                        "aircraft": [(b[5 + 3 * k], le16(b, 6 + 3 * k)) for k in range(14)], "transports": b[47]})
        return out

    def army_reserve(self, img) -> list[dict]:
        out = []
        for s in range(2):
            b = img[ARMY_RESERVE + ARMY_RESERVE_SIZE * s:ARMY_RESERVE + ARMY_RESERVE_SIZE * (s + 1)]
            out.append({"side": s, "budget": le16(b, 0), "materials": le16(b, 2), "infantry": b[4], "armored": b[5],
                        "aircraft": [(b[6 + 3 * k], le16(b, 7 + 3 * k)) for k in range(8)], "trucks": b[30]})
        return out

    def submarines(self, img) -> list[dict]:
        out = []
        for i in range(SUBMARINE_COUNT):
            b = img[SUBMARINES + SUBMARINE_SIZE * i:SUBMARINES + SUBMARINE_SIZE * (i + 1)]
            out.append({"id": i, "name": self.name(b, 0, 14), "class": b[14],
                        "torpedo": b[16], "speed": b[17], "supplies": b[18], "skill": b[19],
                        "x": le16(b, 26), "y": le16(b, 28), "dest_x": le16(b, 35), "dest_y": le16(b, 37),
                        "raw": bytes(b).hex()})
        return out


class Rom(Decoders):
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        assert koei_lz.find_tables(self.data) == LZ_TABLES
        self.rev = self.data[0xFFDB]
        self.off = REVISIONS[self.rev]
        self.charset = load_charset()
        self._cache: dict[int, bytes] = {}
        self.loader_addr, self.loader_end, self.blocks = self.loader()

    # --- generic
    def entry(self, i: int) -> bytes:
        if i not in self._cache:
            p = hirom(self.ptr(self.off["entries"] + 3 * i))
            self._cache[i] = koei_lz.decompress(self.data, p, LZ_TABLES)[0]
        return self._cache[i]

    def entry_addr(self, i: int) -> int:
        return self.ptr(self.off["entries"] + 3 * i)

    def ptr(self, o: int) -> int:
        return int.from_bytes(self.data[o:o + 3], "little")

    def text(self, raw: bytes, i: int = 0, katakana: bool = False) -> str:
        """Game string -> str, up to NUL. Unknown control bytes become [xx]."""
        out, kata = [], katakana
        while i < len(raw) and raw[i]:
            c = raw[i]
            if 0x81 <= c <= 0x9F or c >= 0xE0:
                g = code_glyph(c << 8 | raw[i + 1]) if i + 1 < len(raw) else 0
                out.append(self.charset[g] if g < GLYPH_COUNT else "〓")
                i += 2
                continue
            if c == 0x1B and i + 1 < len(raw):
                k = chr(raw[i + 1])
                if k in "KH":
                    kata = k == "K"
                    i += 2
                elif k == "C":
                    i += 3
                else:
                    out.append(f"[1b{raw[i + 1]:02x}]")
                    i += 2
                continue
            if 0xA1 <= c <= 0xDF:
                out.append(_kana(c, kata))
            elif 0x20 <= c < 0x7F:
                out.append(chr(c))
            elif c == 0x0A:
                out.append("\n")
            else:
                out.append(f"[{c:02x}]")
            i += 1
        return unicodedata.normalize("NFC", "".join(out))  # kana + combining (han)dakuten

    def string(self, addr: int) -> str:
        return self.text(self.data, hirom(addr))

    def strings(self, table: int, n: int) -> list[str]:
        return [self.string(self.ptr(table + 3 * k)) for k in range(n)]

    def glyph(self, g: int) -> list[list[int]]:
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    # --- scenario loader
    def loader(self) -> tuple[int, int, list[dict]]:
        """Parse the scenario loader: (its CPU address, the CPU address after the last copy, blocks).
        Block: {"dst", "size", "src" (file offset), "per" (bytes per scenario, 0 = shared), "first" (first
        scenario using this source; the ship block has two)}."""
        start = self.data.find(LOADER_SIGNATURE)
        assert start > 0 and self.data.find(LOADER_SIGNATURE, start + 1) != start
        seg = self.data[start:start + 0x480]
        blocks, end = [], 0
        for m in re.finditer(rb"\xf4(..)\xf4\x7e\x00\xf4(..)", seg, re.DOTALL):
            size, dst = le16(m.group(1), 0), le16(m.group(2), 0)
            tail = seg[m.end():m.end() + 60]
            f = re.match(rb"\xf4(.)\x00\xf4(..)\x22...((?:\x68){5})", tail, re.DOTALL)
            if f:
                blocks.append({"dst": dst, "size": size, "src": f.group(1)[0] << 16 & 0x3F0000 | le16(f.group(2), 0),
                               "per": 0, "first": 0})
                end = m.end() + f.end()
                continue
            v = re.search(rb"\xa9(..)\x85\x08\xa9(.)\x00\x85\x0a\x22...\xa5\x02\x48\xd4\x00\x22...((?:\x68){5})",
                          tail, re.DOTALL)
            assert v, hex(dst)
            head = tail[:v.start()]
            per = size if dst != 0x726E else 200  # 726E: scenario * 100 shifted left once
            first = 5 if head.startswith(b"\x38\xa3\x18\xe9\x05\x00") else 0  # SEC; LDA $18,S; SBC #5
            blocks.append({"dst": dst, "size": size, "src": v.group(2)[0] << 16 & 0x3F0000 | le16(v.group(1), 0),
                           "per": per, "first": first})
            end = m.end() + v.end()
        assert len(blocks) == 20, len(blocks)
        return 0xC00000 | start - 9, 0xC00000 | start + end, blocks

    def block(self, sc: int, dst: int) -> bytes:
        """The bytes the loader copies to $7E:dst for scenario sc."""
        bl = [b for b in self.blocks if b["dst"] == dst]
        b = max((b for b in bl if b["first"] <= sc), key=lambda b: b["first"])
        o = b["src"] + b["per"] * (sc - b["first"])
        return self.data[o:o + b["size"]]

    def wram_image(self, sc: int) -> bytearray:
        """WRAM bank $7E right after the copies of the scenario loader (plus the static 拠点 table that the game
        sets up at start, with this scenario's owners, so that kyoten() works on it)."""
        img = bytearray(0x10000)
        for dst in sorted({b["dst"] for b in self.blocks}):
            raw = self.block(sc, dst)
            img[dst:dst + len(raw)] = raw
        base, size, n, k = AUX_RUNTIME
        for i in range(n):
            img[base + size * i + k] = 0xFF
        owners = self.kyoten_owners(img)
        for i, st in enumerate(self.kyoten_static()):
            d = KYOTEN + KYOTEN_SIZE * i
            img[d + 15:d + 17] = owners[i].to_bytes(2, "little")
            img[d + 11:d + 15] = st["x"].to_bytes(2, "little") + st["y"].to_bytes(2, "little")
            img[d + 17] = st["flags"]
            img[d + 18:d + 23] = bytes(st["links"] + [0xFF] * (5 - len(st["links"])))
            img[d:d + 11] = st["raw_name"].ljust(11, b"\0")[:11]
        return img

    def format_addr(self, name: str) -> int:
        """CPU address of a printf format used by the verify scripts (FORMATS)."""
        pat, k = FORMATS[name]
        hits = [m.start() for m in re.finditer(re.escape(pat), self.data)]
        return 0xC00000 | hits[k]

    # --- static tables
    def title_ptrs(self) -> list[int]:
        return [self.ptr(self.off["titles"] + 3 * k) for k in range(SCENARIO_COUNT)]

    def titles(self) -> list[dict]:
        out = []
        dates, unk = self.dates(), self.data[self.off["dates"] + 40:self.off["dates"] + 50]
        for sc, s in enumerate(self.strings(self.off["titles"], SCENARIO_COUNT)):
            title = s.partition(":")[2].replace("　", "").strip()
            y, m, d = dates[sc]
            out.append({"id": sc, "title": title, "date": f"{y}-{m:02d}-{d:02d}", "unk": unk[sc]})
        return out

    def dates(self) -> list[tuple[int, int, int]]:
        """Start dates: 10 year words, 10 month bytes, 10 day bytes (copied to $7E:21A6 at game start)."""
        o = self.off["dates"]
        return [(le16(self.data, o + 2 * k), self.data[o + 20 + k], self.data[o + 30 + k])
                for k in range(SCENARIO_COUNT)]

    def type_names(self) -> list[str]:
        return self.strings(self.off["type_names"], 8)

    def air_type_names(self) -> list[str]:
        return self.strings(self.off["air_types"], 11)

    def country_abbr(self) -> list[str]:
        return self.strings(self.off["country_abbr"], COUNTRY_COUNT)

    def kyoten_static(self) -> list[dict]:
        """拠点: name pointers (100), then X words, Y words, flag bytes (bits 0-1 terrain), 5-byte link lists."""
        t = self.off["kyoten"]
        xs, ys, fl, adj = t + 300, t + 500, t + 700, t + 800
        out = []
        for i in range(KYOTEN_COUNT):
            p = hirom(self.ptr(t + 3 * i))
            raw = self.data[p:self.data.index(0, p)]
            links = [v for v in self.data[adj + 5 * i:adj + 5 * i + 5] if v != 0xFF]
            out.append({"id": i, "name": self.text(raw, katakana=True), "raw_name": raw, "x": le16(self.data, xs + 2 * i),
                        "y": le16(self.data, ys + 2 * i), "flags": self.data[fl + i],
                        "terrain": self.data[fl + i] & 3, "links": links})
        return out

    # --- per scenario (ROM)
    def scenario(self, sc: int) -> dict:
        img = self.wram_image(sc)
        return {k: getattr(self, k)(img) for k in (
            "sides", "countries", "bases", "kyoten", "ship_classes", "sub_classes", "ships", "fleets", "admirals",
            "generals", "aircraft", "tanks", "navy_reserve", "army_reserve", "submarines")}

    # --- faces
    def face_palette(self, f: int) -> list[int]:
        o = self.off["face_palettes"] + 32 * face_alt_palette(f)
        return [le16(self.data, o + 2 * k) for k in range(16)]

    def face_tiles(self, f: int) -> bytes:
        return self.entry(FACE_FIRST_ENTRY + f)

    def face_rgb(self, f: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette(f)]
        return [pal[c] for c in tiles_pixels(self.face_tiles(f), FACE_W, FACE_H)]

    # --- map
    def map_bits(self) -> bytes:
        return self.entry(MAP_ENTRY)

    def is_sea(self, x: int, y: int) -> bool:
        m = self.map_bits()
        i = y * MAP_W + x
        return bool(m[i >> 3] >> (7 - (i & 7)) & 1)
