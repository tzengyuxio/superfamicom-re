"""SFC 三國志IV (KOEI, 1994) ROM decoding.

Offsets are file offsets of the headerless 3 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
The LZ decompressor ($C0:F194) is the shared one in tools/koei_lz.py.
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Sangokushi IV (Japan).zip")
LZ_TABLES = 0xF037                      # decompressor table block ($C0:F037), routine at $C0:F194

# Font: 1997 sorted LE16 Shift-JIS codes; glyph number = index in this table (binary search $C1:0DC0).
# Glyph g: 16x16 1bpp, 32 bytes at FONT + 32 g (top-left, top-right, bottom-left, bottom-right 8x8 tiles).
FONT_CODES = 0x14B6A6
GLYPH_COUNT = 0x7CD
FONT = 0x20000
# Game-specific characters in the user area 0xEB9F-0xEBFC (identified from the glyphs and the names using
# them; tools/ext_chars_sheet.py draws them side by side). Not listed: EBF8 (unidentified), EBF9-EBFB
# (circled 戦 内 軍), EBFC (an icon).
EXT_CHARS = {
    0xEB9F: "瓚", 0xEBA0: "昱", 0xEBA1: "彧", 0xEBA2: "郃", 0xEBA3: "蒯", 0xEBA5: "傕", 0xEBA6: "邕", 0xEBA7: "汜",
    0xEBA8: "詡", 0xEBA9: "鄧", 0xEBAA: "兗", 0xEBAB: "龐", 0xEBAC: "繇", 0xEBAD: "邈", 0xEBAE: "騭", 0xEBB0: "闞",
    0xEBB1: "玠", 0xEBB3: "邢", 0xEBB4: "歆", 0xEBB5: "闓", 0xEBB6: "禕", 0xEBB7: "譙", 0xEBB8: "琬", 0xEBB9: "郝",
    0xEBBA: "琮", 0xEBBB: "伷", 0xEBBC: "褚", 0xEBBD: "璜", 0xEBBF: "邳", 0xEBC0: "琦", 0xEBC6: "彤", 0xEBCC: "鄴",
    0xEBD1: "綝", 0xEBD2: "諶", 0xEBD4: "昕", 0xEBD6: "笮", 0xEBD7: "祜", 0xEBDA: "毋", 0xEBDD: "靚", 0xEBDF: "頎",
    0xEBEC: "毗", 0xEBEE: "宓", 0xEBF5: "蹋",
    # not used by person names; read from the glyph only
    0xEBC3: "幷", 0xEBC8: "釭", 0xEBC9: "涪", 0xEBF6: "榮",
}

# Persons 0-461: 35 bytes, see Rom.persons
PERSONS = 0x9AB18
PERSON_COUNT = 462
PERSON_SIZE = 35
BIRTH_BASE = 100                        # +25 = 生年 - 100
STATS = ["統率", "武力", "知力", "政治", "魅力"]

# Scenarios: menu lines "189[12\\ 董卓、都洛陽を制す" (year, "[" = 年, month, "\\" = 月, title), NUL-terminated
SCENARIO_COUNT = 6
SCENARIO_MENU = 0xBB5A2
# Per-scenario LZ streams (6 long pointers each), decompressed by the game into WRAM when a scenario starts
SCENARIO_PERSONS = 0xCAB8A               # -> $7E:73B2, 17-byte records, see Rom.scenario_persons
SCENARIO_CITIES = 0x107B38               # -> $7E:B872, 87-byte records (43), see Rom.scenario_cities
SCENARIO_FORCES = 0x14D6B5               # -> $7E:C70F, 51-byte records (25), see Rom.scenario_forces
PERSONS_WRAM, CITIES_WRAM, FORCES_WRAM = 0x73B2, 0xB872, 0xC70F
SP_SIZE, CITY_SIZE, FORCE_SIZE = 17, 87, 51
# Person lists of a city record: offset -> meaning
CITY_LISTS = {1: "武将", 3: "在野A", 5: "在野B", 9: "異民族", 11: "未解A", 13: "未解B"}
FORCE_COUNT = 25
# Bits the loader changes after decompressing ({byte: mask}): force +10/+11 (unknown), and for the emperors'
# forces of scenarios 5-6 (曹丕 劉備 / 曹叡 孫権 劉禅) force +3 bit 6 and the ruler's ability bit 28 (person +12 bit 4)
FORCE_RUNTIME = {3: 0x40, 10: 0xFF, 11: 0xFF}
PERSON_RUNTIME = {12: 0x10}

# Special abilities: bit -> name; names are 24 x 5 bytes at ABILITY_NAMES ("外交 情報 ...")
ABILITY_NAMES = 0x7DC6C
ABILITY_BITS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]

# Cities 0-42: 29 bytes = 2 unknown bytes (not map coordinates), unknown flags, name (5 bytes SJIS),
# reading (6 half-width), 0, neighbouring cities (14, FF-padded; the order matters for FIELD_MAPS)
CITIES = 0xBB09D
CITY_COUNT = 43
CITY_NAME_SIZE = 29
# Map view per city: 43 x (x, y) LE16 in pixels; the city's castle icon (2x2 tiles) is at
# tile ((x + 112) / 8, (y + 96) / 8) of the big map
CITY_VIEW = 0x10A397

# Big map: one mode-7 plane, 128 x 128 tilemap (rows 0-95 used = 1024 x 768 px) and 256 8bpp tiles, two LZ
# streams behind the pointers at MAP_POINTERS ($DB:1AD1, $DB:3533), loaded by $C3:0A05. CGRAM: rows 3-7 from
# MAP_PALETTE (160 bytes), rows 12-13 cycle through the 4 frames of MAP_WATER (64 bytes each), rows 14-15 from
# MAP_PALETTE2.
MAP_POINTERS = 0x1B5490
MAP_W, MAP_H = 128, 96
MAP_PALETTE = 0x12BFC8
MAP_WATER = [0x12C3E8 + 0x40 * k for k in range(4)]
MAP_PALETTE2 = 0x12C0A8

# Battle maps 0-87 (loader $C7:5CA7): hex grid of 20 columns x 11 rows (odd columns 10), with three streams
# per map in the pointer table BATTLE_TABLE ($CA:E248): m = deployment (220 bytes), 88 + m = terrain (220),
# 176 + m = BG tilemaps (two 40 x 22 LE16 layers: BG1 features, BG2 ground). Maps 0-44 are field battles:
# map = FIELD_MAPS[6 * target + k], k = the attacker's position in the target's neighbour list ($D1:9773);
# maps 45-87 are siege battles of city m - 45 ($7E:3DAE = 0). Tiles at VRAM tile 0x100 ($C7:5321): field
# stream 0 of BATTLE_CHARS_TABLE (608 4bpp tiles), siege stream 1 (368 tiles). Palettes: field from a set of
# BATTLE_PALETTES (4 sets of 7 x 32 bytes: palettes 4, 5, 6, then 4 animation frames of palette 7), siege
# palettes 4-6 from a set of SIEGE_PALETTES (4 sets of 3 x 32 bytes). Set 3 is the one used in month 12;
# that the 4 sets are the seasons is a guess.
BATTLE_TABLE = 0xAE248
BATTLE_COUNT = 88
FIELD_COUNT = 45
FIELD_MAPS = 0x13B737
BATTLE_W, BATTLE_H = 20, 11
BATTLE_TILES_W, BATTLE_TILES_H = 40, 22
BATTLE_CHARS_TABLE = 0x14E540
BATTLE_TILE0 = 0x100
BATTLE_PALETTES = 0x13BBEE
SIEGE_PALETTES = 0x13BF6E
BATTLE_PALETTE_SETS = 4

# Faces: 40x48 = 5x6 4bpp tiles row-major (960 bytes), decompressed by $C3:5823 (portraits) or $C3:5303
# (composed). Face code bit 15 clear: portrait 0-338 from five pointer tables of 72 (last 51) streams.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_COUNT = 339
PORTRAIT_TABLES = [0x1DFD6B, 0x1FC80A, 0x25B1F3, 0x1ABF4A, 0x21A0CD]
PORTRAIT_PALETTE_NO = 0x10BBFB           # byte per portrait: palette number ($C3:598B)
FACE_PALETTES = 0x12C4E8                 # 32 bytes per palette number ($C3:5AE0)
# Composed faces (code bit 15 set): bits 0-3 pack, 4-5 top face, 6-7 bottom face, 8-10 eyes, 11-12 mouth;
# pack p is streams 6p..6p+5 of PACK_TABLE; palette 0. Offsets in bytes of the 960-byte face.
PACK_TABLE = 0x1ED9D4
PACK_COUNT = 16
PACK_CUT = 0xC38D8F & 0x3FFFFF           # 16 x LE16: top face bytes [0, cut), bottom face from cut
PACK_EYES = 0xC38DAF & 0x3FFFFF          # 16 x LE16: eye part offset
PACK_MOUTH = 0xC38DCF & 0x3FFFFF         # 16 x LE16: mouth part offset


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


def text(raw: bytes) -> str:
    """Game string -> str: Shift-JIS (cp932) plus EXT_CHARS; stops at NUL."""
    out, i = [], 0
    while i < len(raw) and raw[i]:
        c = raw[i]
        if 0x81 <= c < 0xA0 or 0xE0 <= c < 0xFD:
            code = c << 8 | raw[i + 1]
            out.append(EXT_CHARS.get(code) or bytes(raw[i:i + 2]).decode("cp932", "replace"))
            i += 2
        else:
            out.append(bytes([c]).decode("cp932", "replace"))
            i += 1
    return "".join(out)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        assert koei_lz.find_tables(self.data) == LZ_TABLES
        self._cache: dict[int, bytes] = {}

    # --- generic ---
    def ptr(self, table: int, i: int) -> int:
        """File offset of long pointer i of a pointer table."""
        return hirom(int.from_bytes(self.data[table + 3 * i:table + 3 * i + 3], "little"))

    def stream(self, p: int) -> bytes:
        """Decompressed LZ stream at file offset p."""
        if p not in self._cache:
            self._cache[p] = koei_lz.decompress(self.data, p, LZ_TABLES)[0]
        return self._cache[p]

    def glyph_codes(self) -> list[int]:
        return [le16(self.data, FONT_CODES + 2 * g) for g in range(GLYPH_COUNT)]

    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g."""
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    # --- master tables ---
    def abilities(self) -> dict[int, str]:
        names = self.data[ABILITY_NAMES:ABILITY_NAMES + 5 * 24].decode("cp932").replace("\0", " ").split()
        return dict(zip(ABILITY_BITS, names))

    def scenario_titles(self) -> list[dict]:
        out, p = [], SCENARIO_MENU
        for _ in range(SCENARIO_COUNT):
            end = self.data.index(b"\0", p)
            line = self.data[p:end].decode("cp932")
            year, rest = line.split("[", 1)
            month, title = rest.split("\\", 1)
            out.append({"year": int(year), "month": int(month), "title": title.strip()})
            p = end + 1
        return out

    def persons(self) -> list[dict]:
        """+0 name (9), +9 reading (11, half-width), +20 face code LE16, +22 relation LE16 (FFFF none),
        +24 相性?, +25 生年 - 100, +26..29 unknown, +30 統率 武力 知力 政治 魅力."""
        out = []
        for pid in range(PERSON_COUNT):
            o = PERSONS + PERSON_SIZE * pid
            r = self.data[o:o + PERSON_SIZE]
            p = {"id": pid, "offset": o, "raw": r, "name": text(r[0:9]), "reading": text(r[9:20]),
                 "face": le16(r, 20), "relation": le16(r, 22), "compat": r[24], "born": BIRTH_BASE + r[25],
                 "unknown26": r[26], "unknown27": r[27:30].hex()}
            for k, s in enumerate(STATS):
                p[s] = r[30 + k]
            out.append(p)
        return out

    def cities(self) -> list[dict]:
        out = []
        for i in range(CITY_COUNT):
            o = CITIES + CITY_NAME_SIZE * i
            r = self.data[o:o + CITY_NAME_SIZE]
            vx, vy = le16(self.data, CITY_VIEW + 4 * i), le16(self.data, CITY_VIEW + 4 * i + 2)
            out.append({"id": i, "unknown0": r[0], "unknown1": r[1], "flags": r[2], "name": text(r[3:8]),
                        "reading": text(r[8:14]), "neighbours": [c for c in r[15:29] if c != 0xFF],
                        "view_x": vx, "view_y": vy, "map_x": (vx + 112) // 8, "map_y": (vy + 96) // 8})
        return out

    # --- scenarios ---
    def scenario_stream(self, table: int, sc: int) -> bytes:
        return self.stream(self.ptr(table, sc))

    def scenario_persons(self, sc: int) -> list[dict]:
        """17-byte records (WRAM $7E:73B2), referred to elsewhere by 1-based record number:
        +0 next record of the same list (1-based, FFFF end), +2..5 unknown, +6 忠誠, +7 city, +8 force (FF none),
        +9 special abilities (32-bit LE, ABILITY_BITS), +13 unknown LE16, +15 person id LE16."""
        raw = self.scenario_stream(SCENARIO_PERSONS, sc)
        out = []
        for k in range(len(raw) // SP_SIZE):
            r = raw[SP_SIZE * k:SP_SIZE * (k + 1)]
            out.append({"no": k + 1, "raw": r, "next": le16(r, 0), "unknown2": r[2:6].hex(), "loyalty": r[6],
                        "city": r[7], "force": r[8], "abilities": int.from_bytes(r[9:13], "little"),
                        "unknown13": le16(r, 13), "person": le16(r, 15)})
        return out

    def scenario_cities(self, sc: int) -> list[dict]:
        """87-byte records (WRAM $7E:B872): +0 next city of the owner's list (FF end), person lists (1-based
        scenario person record of the head, FFFF empty; next at person +0): +1 officers (head = 太守), +3 and +5
        unaffiliated, +9 tribe members, +11 and +13 unknown; +15 人口 / 100, +17 金, +19 兵糧, +21 兵士 (LE16),
        +23 owner force (FF none), +24 開発 +25 治水 +26 商業 +27 技術, +28 unknown (1-3), +29 民忠 +30 士気
        +31 訓練, +32 弩 +34 強弩 +36 軍馬 +38 連弩 +40 発石 (LE16). See docs/ROM_FORMAT.md."""
        raw = self.scenario_stream(SCENARIO_CITIES, sc)
        out = []
        for i in range(CITY_COUNT):
            r = raw[CITY_SIZE * i:CITY_SIZE * (i + 1)]
            out.append({"id": i, "raw": r, "next": r[0], "governor": le16(r, 1),
                        "lists": {k: le16(r, k) for k in CITY_LISTS}, "population": le16(r, 15) * 100,
                        "gold": le16(r, 17), "food": le16(r, 19), "soldiers": le16(r, 21), "owner": r[23],
                        "develop": r[24], "flood": r[25], "commerce": r[26], "tech": r[27], "unknown28": r[28],
                        "loyalty": r[29], "morale": r[30], "training": r[31], "crossbow": le16(r, 32),
                        "strong_crossbow": le16(r, 34), "horses": le16(r, 36), "repeating_crossbow": le16(r, 38),
                        "catapult": le16(r, 40)})
        return out

    def scenario_members(self, sc: int) -> dict[int, tuple[int, int]]:
        """1-based scenario person record -> (city, city list offset) from the city person lists."""
        sp = self.scenario_persons(sc)
        out = {}
        for c in self.scenario_cities(sc):
            for off, k in c["lists"].items():
                while k != 0xFFFF and k not in out:
                    out[k] = (c["id"], off)
                    k = sp[k - 1]["next"]
        return out

    def scenario_forces(self, sc: int) -> list[dict]:
        """51-byte records (WRAM $7E:C70F): +0 ruler (1-based scenario person record, FFFF = empty slot),
        +2 first city of the force's city list (FF none; next city at city +0), +8 unknown,
        +12.. friendship towards forces 0-17. Forces 21-24 are the four tribes. "seat" = the ruler's city."""
        raw = self.scenario_stream(SCENARIO_FORCES, sc)
        sp = self.scenario_persons(sc)
        cities = self.scenario_cities(sc)
        out = []
        for i in range(FORCE_COUNT):
            r = raw[FORCE_SIZE * i:FORCE_SIZE * (i + 1)]
            ruler = le16(r, 0)
            chain, c = [], r[2]
            while c != 0xFF and len(chain) < CITY_COUNT:
                chain.append(c)
                c = cities[c]["raw"][0]
            out.append({"id": i, "raw": r, "ruler": ruler, "first_city": r[2], "cities": chain,
                        "seat": sp[ruler - 1]["city"] if ruler != 0xFFFF else None, "unknown8": r[8],
                        "friendship": list(r[12:30])})
        return out

    # --- faces ---
    def face_palette(self, code: int) -> list[int]:
        n = 0 if code & 0x8000 else self.data[PORTRAIT_PALETTE_NO + code]
        return [le16(self.data, FACE_PALETTES + 32 * n + 2 * i) for i in range(16)]

    def face_palette_number(self, code: int) -> int:
        return 0 if code & 0x8000 else self.data[PORTRAIT_PALETTE_NO + code]

    def portrait_tiles(self, n: int) -> bytes:
        t, k = min(n // 72, 4), n - 72 * min(n // 72, 4)
        return self.stream(self.ptr(PORTRAIT_TABLES[t], k))[:FACE_BYTES]

    def pack_part(self, pack: int, k: int) -> bytes:
        return self.stream(self.ptr(PACK_TABLE, 6 * pack + k))[:FACE_BYTES]

    def face_tiles(self, code: int) -> bytes:
        """960 bytes of 4bpp tiles of face code (portrait, or composed as $C3:5303 does it)."""
        if not code & 0x8000:
            return self.portrait_tiles(code)
        pack, a, b, c, d = code & 15, code >> 4 & 3, code >> 6 & 3, code >> 8 & 7, code >> 11 & 3
        part = [self.pack_part(pack, k) for k in range(6)]
        cut = le16(self.data, PACK_CUT + 2 * pack)
        out = bytearray(part[a][:cut] + part[b][cut:])
        eyes, eo = part[c], le16(self.data, PACK_EYES + 2 * pack)
        n = 0x40 if pack in (0, 2, 8, 13) else 0x20 if pack == 4 else 0x60
        out[eo:eo + n] = eyes[eo:eo + n]
        if pack == 4:
            out[0x180:0x1E0] = eyes[0x180:0x1E0]
        mouth, mo = part[d], le16(self.data, PACK_MOUTH + 2 * pack)
        n = 0x60 if pack in (7, 10, 11, 14, 15) else 0x40
        out[mo:mo + n] = mouth[mo:mo + n]
        if pack in (1, 9, 10, 14, 15):
            n = 0x60 if pack == 10 else 0x20
            o = 0x2A0 if pack == 10 else 0x240 if pack == 14 else 0x220
            out[o:o + n] = mouth[o:o + n]
        return bytes(out)

    def face_pixels(self, code: int) -> list[int]:
        """40x48 colour numbers of a face code, row-major."""
        tiles = self.face_tiles(code)
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, code: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette(code)]
        return [pal[v] for v in self.face_pixels(code)]

    # --- big map ---
    def map_tilemap(self) -> bytes:
        """128 x 128 mode-7 tile numbers (rows 0-95 used)."""
        return self.stream(self.ptr(MAP_POINTERS, 0))

    def map_chars(self) -> bytes:
        """256 mode-7 tiles, 64 bytes each (one colour number per pixel)."""
        return self.stream(self.ptr(MAP_POINTERS, 1))

    def map_cgram(self, water: int = 0) -> bytes:
        """512-byte CGRAM image of the big map with water animation frame `water` (other rows 0)."""
        cg = bytearray(512)
        cg[0x60:0x100] = self.data[MAP_PALETTE:MAP_PALETTE + 0xA0]
        cg[0x180:0x1C0] = self.data[MAP_WATER[water]:MAP_WATER[water] + 0x40]
        cg[0x1C0:0x200] = self.data[MAP_PALETTE2:MAP_PALETTE2 + 0x40]
        return bytes(cg)

    def map_pixels(self) -> list[int]:
        """MAP_W*8 x MAP_H*8 colour numbers (0-255), row-major."""
        tm, ch = self.map_tilemap(), self.map_chars()
        w = MAP_W * 8
        out = [0] * (w * MAP_H * 8)
        for ty in range(MAP_H):
            for tx in range(MAP_W):
                t = tm[ty * 128 + tx]
                for y in range(8):
                    o = (ty * 8 + y) * w + tx * 8
                    out[o:o + 8] = ch[t * 64 + y * 8:t * 64 + y * 8 + 8]
        return out

    def map_rgb(self, water: int = 0) -> list[tuple[int, int, int]]:
        cg = self.map_cgram(water)
        pal = [bgr555_rgb(le16(cg, 2 * i)) for i in range(256)]
        return [pal[v] for v in self.map_pixels()]

    # --- battle maps ---
    def battle_stream(self, k: int) -> bytes:
        return self.stream(self.ptr(BATTLE_TABLE, k))

    def field_map(self, target: int, attacker: int) -> int:
        """Field battle map number for an attack on `target` from neighbouring city `attacker`."""
        k = self.cities()[target]["neighbours"].index(attacker)
        return self.data[FIELD_MAPS + 6 * target + k]

    def battle_maps(self) -> list[dict]:
        """88 maps: kind field/siege, city (siege: the city), uses (field: every (target, attacker) pair
        that picks it), deploy / terrain as 11 rows x 20 columns of bytes, layers = 2 x 880 LE16 BG entries."""
        uses: dict[int, list[tuple[int, int]]] = {}
        for c in self.cities():
            for k, n in enumerate(c["neighbours"]):
                uses.setdefault(self.data[FIELD_MAPS + 6 * c["id"] + k], []).append((c["id"], n))
        n = BATTLE_TILES_W * BATTLE_TILES_H
        out = []
        for m in range(BATTLE_COUNT):
            dep, ter, bg = (self.battle_stream(m), self.battle_stream(BATTLE_COUNT + m),
                            self.battle_stream(2 * BATTLE_COUNT + m))
            out.append({"id": m, "kind": "field" if m < FIELD_COUNT else "siege",
                        "city": m - FIELD_COUNT if m >= FIELD_COUNT else None, "uses": uses.get(m, []),
                        "deploy": [list(dep[BATTLE_W * r:BATTLE_W * (r + 1)]) for r in range(BATTLE_H)],
                        "terrain": [list(ter[BATTLE_W * r:BATTLE_W * (r + 1)]) for r in range(BATTLE_H)],
                        "layers": [[le16(bg, 2 * (n * L + i)) for i in range(n)] for L in range(2)]})
        return out

    def battle_chars(self, siege: bool = False) -> bytes:
        """4bpp tiles loaded at VRAM tile BATTLE_TILE0."""
        return self.stream(self.ptr(BATTLE_CHARS_TABLE, int(siege)))

    def battle_palettes(self, pset: int, siege: bool = False, frame: int = 0) -> dict[int, list[int]]:
        """CGRAM palettes 4-6 (field: and 7, animation frame `frame`) of palette set pset."""
        if siege:
            base = SIEGE_PALETTES + 0x60 * pset
            offs = {4: base, 5: base + 0x20, 6: base + 0x40}
        else:
            base = BATTLE_PALETTES + 0xE0 * pset
            offs = {4: base, 5: base + 0x20, 6: base + 0x40, 7: base + 0x60 + 0x20 * frame}
        return {p: [le16(self.data, o + 2 * i) for i in range(16)] for p, o in offs.items()}

    def battle_rgb(self, m: int, pset: int = 3) -> list:
        """320 x 176 RGB tuples (None = backdrop) of battle map m: BG2 (layer 1), BG1 (layer 0) on top,
        colour 0 transparent."""
        siege = m >= FIELD_COUNT
        bg = self.battle_stream(2 * BATTLE_COUNT + m)
        n = BATTLE_TILES_W * BATTLE_TILES_H
        layers = [[le16(bg, 2 * (n * L + i)) for i in range(n)] for L in range(2)]
        ch = self.battle_chars(siege)
        pals = {p: [bgr555_rgb(c) for c in v] for p, v in self.battle_palettes(pset, siege).items()}
        w = BATTLE_TILES_W * 8
        out: list = [None] * (w * BATTLE_TILES_H * 8)
        for L in (1, 0):
            for i, e in enumerate(layers[L]):
                t = (e & 0x3FF) - BATTLE_TILE0
                if not 0 <= t < len(ch) // 32 or (e >> 10 & 7) not in pals:
                    continue
                pal = pals[e >> 10 & 7]
                px = decode_tile(ch[32 * t:32 * t + 32])
                ty, tx = divmod(i, BATTLE_TILES_W)
                for k, v in enumerate(px):
                    if not v:
                        continue
                    y, x = divmod(k, 8)
                    if e & 0x8000:
                        y = 7 - y
                    if e & 0x4000:
                        x = 7 - x
                    out[(ty * 8 + y) * w + tx * 8 + x] = pal[v]
        return out
