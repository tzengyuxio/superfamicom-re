"""SFC 横山光輝 三国志2 (Angel, 1993) ROM decoding.

The ROM is a headerless 1.5 MB LoROM image run from the FastROM banks: CPU $bb:8000-$FFFF (bb = $80-$AF) = file
0x8000 (bb & 0x7F) + (addr - 0x8000). The engine is the one of 横山光輝 三国志 (yokoyama/), reassembled: 16-bit
text codes drawn by $80:8C2E (data/charset.txt, a redrawn font), the same LZSS, sprite faces and a mode-7 map. The
tables are new: 239 names (229 persons), 35 countries, 16 factions, 3 scenarios. See docs/ROM_FORMAT.md.
"""
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
from paths import ORIGINAL

DEFAULT_ROM = os.path.join(ORIGINAL, "Yokoyama Mitsuteru Sangokushi 2 (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

# Text ($80:8C2E, A = one code): 0x200-0x5FF = 16x16 glyph at FONT16 + 32 (code - 0x200) (8x8 tiles TL BL TR BR,
# one byte per row); 0x100-0x1FF = 8x16 glyph at FONT8 + 16 (code - 0x100); below 0x100: control codes ($80:8D03).
TEXT_OUT = 0x808C2E
FONT16, FONT16_COUNT = 0x9A8000, 0x400
FONT8 = 0x99A000
TEXT_NEWLINE, TEXT_END = 0x000A, 0x0000
# Control codes ($80:8D03): what they print. F0 = name of person $0109, F1 = country name ($0113), F2 / F6 =
# 3-digit number ($67 / $71), F3 / F7 = 4-digit ($69 / $73), F4 / F8 = 5-digit ($6B / $75), F5 / F9 = ($6D /
# $77), any other code below 0x100 = name of person $010B.
CONTROL = {0xF0: "{武将:$0109}", 0xF1: "{国:$0113}", 0xF2: "{数3:$67}", 0xF3: "{数4:$69}", 0xF4: "{数5:$6B}",
           0xF5: "{$6D}", 0xF6: "{数3:$71}", 0xF7: "{数4:$73}", 0xF8: "{数5:$75}", 0xF9: "{$77}"}

# The reading of 諸葛亮 is drawn with six half-width glyphs 1FA-1FF that together show ショカツリョウ
LIGATURE = {0x1FA: "ショカツリョウ", 0x1FB: "", 0x1FC: "", 0x1FD: "", 0x1FE: "", 0x1FF: ""}

PERSON_COUNT = 229               # persons of the scenarios; the name table has 239 (229-238: generic names)
NAME_COUNT = 239
NAMES = 0x8C8000                 # 239 x 8: 3 codes (0x200 = none) + reading pointer ($8C:xxxx)
PERSON_SIZE = 17
PERSON_TABLES = 0x8C90C2         # 3 bank-$8C pointers: persons of 189 / 200 / 215
PERSON_WRAM, PERSON_WRAM_SIZE = 0x0700, 24   # 7-byte head + the 17-byte ROM record
PLACE_SIZE = 5
PLACES = [0x8CBE6D, 0x8CC2E6, 0x8CC75F]       # 229 x 5 per scenario ($99:E5E9)
COUNTRY_COUNT, COUNTRY_SIZE = 35, 18
COUNTRIES = [0x8CD469, 0x8CD6DF, 0x8CD955]    # 35 x 18 per scenario ($99:E4FF)
COUNTRY_WRAM, COUNTRY_WRAM_SIZE = 0x1C92, 20  # the ROM record + 2 bytes
COUNTRY_WRAM_BYTES = 0x1F4C - COUNTRY_WRAM    # the loader stops at $1F4C: country 34 has no +18 / +19
COUNTRY_NAMES = 0x8CD21B                      # 35 x 2 codes; reading pointers follow (35 x 2 bytes)
FACTION_COUNT, FACTION_SIZE = 16, 3
FACTIONS = [0x8CDBCB, 0x8CDBFB, 0x8CDC2B]     # 16 x 3 per scenario ($99:E47D): ruler, 0, 0
FACTION_WRAM, FACTION_WRAM_SIZE = 0x1F4C, 4   # 0, the ROM record
SCENARIO_YEARS = [189, 200, 215]              # $99:E447: $017C = 0xBD / 0xC8 / 0xD7, month $017E = 0
SCENARIO_TITLES = ["桃園の誓い", "群雄割拠", "三国時代"]
LOADER = 0x99E436                # JSL from $80:8085; returns to $80:8089
LOADER_DONE = 0x808089
# Difficulty ($03EB = menu item 0-2, $0178 = 0x88 / 0x155 / 0x222): $80:8103 replaces 金 and 米 of all countries
# with a table for 上級 and 初級 (35 x (金, 米) LE16); 中級 keeps the scenario's values
DIFFICULTIES = ["上級", "中級", "初級"]
DIFFICULTY_GOLD_FOOD = {0: [0x8CEBAF, 0x8CECC7, 0x8CEDDF], 2: [0x8CEB23, 0x8CEC3B, 0x8CED53]}

# Person record (ROM, 17 bytes; WRAM +7). The WRAM head: +0 faction | 0x80, +1 country | 0x80 for persons
# placed in a country at the start (placement kind 0), else 0; +2-+6 0.
PERSON_FIELDS = [  # (name, offset, size)
    ("官位", 0, 1), ("レベル", 1, 1), ("経験値", 2, 1), ("体力", 3, 1), ("忠誠度", 4, 1), ("人望", 5, 1),
    ("士気", 6, 1), ("疲労度", 7, 1), ("武器", 8, 1), ("武器2", 9, 1), ("兵士数", 10, 2), ("移動力", 12, 1),
    ("武力", 13, 1), ("兵法力", 14, 1), ("政治力", 15, 1), ("統率力", 16, 1),
]
# Country record (ROM, 18 bytes)
COUNTRY_FIELDS = [
    ("勢力", 0, 1), ("太守", 1, 1), ("金", 2, 2), ("米", 4, 2), ("民", 6, 2), ("収穫高", 8, 2), ("産業値", 10, 2),
    ("統治度", 12, 1), ("防災値", 13, 1), ("税率", 14, 1), ("城塞値", 15, 1), ("開発度", 16, 1), ("砦", 17, 1),
]
# Placement (5 bytes): kind, country, related person (or faction for kind 3), year, 0. The loader only uses kind 0
# (in service in the country; the head gets faction and country); the other kinds are read like 横山光輝 三国志
# (unverified here): 1 在野 (country, year), 2 親族 (person, year), 3 勢力 (country, faction, year), 4 推挙 (country,
# person, year), 5 登用 (country, person, year); FF = absent from the scenario (all bytes FF)
PLACE_KINDS = {0: "仕官", 1: "在野", 2: "親族", 3: "勢力", 4: "推挙", 5: "登用", 0xFF: "不在"}
KANI = {0: "ーー", 1: "軍師", 2: "将軍", 3: "参謀"}   # 官位 as the detail screen shows it

# Faces ($80:8968, person $F9): 12 part numbers at FACE_PARTS + 12 p go to $FB-$0106; each part is copied in
# chunks into the sprite tile buffer $7E:8000 (16 8x8 tiles per row, 0x200 bytes per tile row), which is then
# DMA'd (0x1000 bytes) to the OBJ tiles. Part k: (source CPU address, bytes per part, chunk size, buffer offsets
# of the consecutive chunks); FF = none for the parts in FACE_OPTIONAL.
FACE_PARTS = 0x9BA789
FACE_SLOTS = [
    (0x958010, 0x100, 0x80, [0x000, 0x200]),
    (0x958610, 0x300, 0x80, [0x400, 0x800, 0xC00, 0x600, 0xA00, 0xE00]),
    (0x968000, 0x200, 0x80, [0x180, 0x580, 0x380, 0x780]),
    (0x978000, 0x100, 0x40, [0x940, 0xD40, 0xB40, 0xF40]),
    (0x95E610, 0x200, 0x80, [0x980, 0xD80, 0xB80, 0xF80]),
    (0x97B900, 0x100, 0x40, [0x0C0, 0x4C0, 0x2C0, 0x6C0]),
    (0x96C800, 0x100, 0x40, [0x8C0, 0xCC0, 0xAC0, 0xEC0]),
    (0x988000, 0x100, 0x40, [0x100, 0x500, 0x300, 0x700]),
    (0x98CC00, 0x80, 0x40, [0x080, 0x280]),
    (0x98E000, 0x80, 0x40, [0x480, 0x680]),
    (0x98EC00, 0x80, 0x40, [0x880, 0xA80]),
    (0x98EC00, 0x80, 0x40, [0xC80, 0xE80]),   # the same part table as part 10, lower in the face
]
FACE_OPTIONAL = {3, 5, 6, 7, 8, 9, 10, 11}
FACE_BUFFER = 0x1000
FACE_PALETTES = 0x9BB2C9         # 16 colours per person: OBJ palette 0 ($80:891A -> CGRAM shadow $0500)
META_TABLE = 0x81826B            # metasprites ($81:8196): bank-$81 pointers; record = count, count x (dx, dy, tile,
FACE_META = 0                    # attr); 0-3 are the face (0 = still; 1-3 change the eyes and the mouth)
# $81:8087: five persons have their own 4 metasprites (base + frame; $4A set: + 0x18, the face on the other side)
FACE_META_BASE = {0x21: 4, 0x4A: 8, 0x91: 12, 0xB8: 16, 0xE1: 20}   # 夏侯惇 胡軫 張飛 文醜 陳宮
FACE_ORIGIN = (24, 32)           # metasprite origin inside the 48 x 64 box
FACE_W, FACE_H = 48, 64

# Strategic map (mode 7, 1024 x 1024 at 1/4 scale): $91:8000 decompresses MAP_STREAM (lz) to $7E:8000, $81:A98C
# interleaves every 16 bytes (8 tilemap bytes, 8 pixel bytes -> VRAM words), $91:8031 draws the forts of each
# country, $91:81AF the marching armies, and the 32 KB go to VRAM 0. The map pixels use colours 0x20-0x5F
# (MAP_PALETTE, 64 colours; 0x50-0x57 cycle on screen in two groups of 4).
MAP_STREAM, MAP_TILES = 0x91827D, 128
MAP_POSITIONS = 0x8CDC5B         # 35 x (x, y) in 16-pixel units of the 1024 x 1024 map
MAP_FORT_TILES = 0x918197        # 6 x 4 tile numbers, one 2 x 2 piece per bit of the country's 砦 byte
MAP_FORT_CELLS = [(0, -1), (2, -1), (3, 1), (2, 3), (0, 3), (-1, 1)]   # top-left (column, row) of each piece,
# from the country's cell (2 x - 1, 2 y - 1)
# Marching armies ($91:81AF): a person whose WRAM head has +0 = 0x80 | faction (bits 0x60 clear) and +1 = column x
# (not 0xFF, bit 0x80 clear: in a country), +2 = row y is drawn at tile (2 x + (y & 1), 2 y): tiles a, faction
# 0xE0 + f on the first row and b, c below; (a, b, c) = MAP_ARMY_TILES, or the next 6 bytes on when +0 has 0x10
MAP_ARMY_TILES = 0x918274
MAP_PALETTE, MAP_COLOURS = 0xA0CC8F, (0x20, 0x60)
# Country markers: OBJ 1 + c at screen (4 x - 2, 4 y - 2) (the map at 1/4 scale), 8 x 8, tile 0xC8 + (f & 7) +
# 0x10 (f >> 3), palette 6 + (f >> 3) (f = faction, 15 for none); the marker colour (inferred) is colour 8 + (f & 7) of
# that palette (MAP_MARKER_COLOURS, 2 x 16 colours = OBJ palettes 6-7)
MAP_MARKER_COLOURS = 0x91CFF4


def off(addr: int) -> int:
    """LoROM CPU address -> file offset."""
    return (addr >> 16 & 0x7F) * 0x8000 + (addr & 0x7FFF)


def cpu(o: int) -> int:
    """File offset -> FastROM CPU address ($80-)."""
    return 0x800000 | (o // 0x8000) << 16 | 0x8000 + o % 0x8000


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]


def load_charset(path: str = CHARSET) -> dict[int, str]:
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            first, chars = line.rstrip("\n").split("\t")
            for k, c in enumerate(chars):
                out[int(first, 16) + k] = c
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return tuple((c >> s & 31) << 3 | (c >> s & 31) >> 2 for s in (0, 5, 10))


def palette(raw: bytes) -> list[tuple[int, int, int]]:
    return [bgr555_rgb(le16(raw, 2 * i)) for i in range(len(raw) // 2)]


def lz(data: bytes, addr: int) -> bytes:
    """Decompress the stream at CPU address addr ($81:A8F0): LE16 output size, then flag bytes read LSB first;
    1 = literal byte, 0 = LE16 word w: copy (w & 15) + 3 bytes from distance w >> 4 back (positions before the
    start read as 0). The same format as 横山光輝 三国志."""
    o = off(addr)
    size = le16(data, o)
    o += 2
    out = bytearray()
    bits = n = 0
    while len(out) < size:
        if n == 0:
            bits, n = data[o], 8
            o += 1
        n -= 1
        flag, bits = bits & 1, bits >> 1
        if flag:
            out.append(data[o])
            o += 1
        else:
            w = le16(data, o)
            o += 2
            for _ in range((w & 15) + 3):
                p = len(out) - (w >> 4)
                out.append(out[p] if p >= 0 else 0)
    return bytes(out[:size])


def decode_tile4(raw: bytes) -> list[int]:
    """One 4bpp SNES tile (32 bytes) -> 64 colour numbers, row-major."""
    out = []
    for y in range(8):
        p0, p1, p2, p3 = raw[2 * y], raw[2 * y + 1], raw[16 + 2 * y], raw[17 + 2 * y]
        for x in range(7, -1, -1):
            out.append((p0 >> x & 1) | (p1 >> x & 1) << 1 | (p2 >> x & 1) << 2 | (p3 >> x & 1) << 3)
    return out


def decode_fields(raw: bytes, fields) -> dict:
    return {name: raw[o] if n == 1 else le16(raw, o) for name, o, n in fields}


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.charset = load_charset()
        self.persons_at = [0x8C0000 | self.u16(PERSON_TABLES + 2 * k) for k in range(3)]
        assert self.persons_at == [0x8C90C8, 0x8C9FFD, 0x8CAF32], self.persons_at

    def u8(self, addr: int) -> int:
        return self.data[off(addr)]

    def u16(self, addr: int) -> int:
        return le16(self.data, off(addr))

    def raw(self, addr: int, n: int) -> bytes:
        return self.data[off(addr):off(addr) + n]

    # --- text ---
    def char(self, code: int) -> str:
        if code in CONTROL:
            return CONTROL[code]
        if code in LIGATURE:
            return LIGATURE[code]
        return self.charset.get(code, f"[{code:X}]")

    def text(self, codes) -> str:
        return "".join("\n" if c == TEXT_NEWLINE else self.char(c) for c in codes)

    def codes_at(self, addr: int, limit: int = 4000) -> list[int]:
        out = []
        while len(out) < limit:
            c = self.u16(addr + 2 * len(out))
            if c == TEXT_END:
                break
            out.append(c)
        return out

    def glyph16(self, code: int) -> list[list[int]]:
        """16x16 bitmap (rows of 0/1) of a code 0x200-0x5FF."""
        raw = self.raw(FONT16 + 32 * (code - 0x200), 32)
        rows = [[0] * 16 for _ in range(16)]
        for t, (tx, ty) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
            for r in range(8):
                b = raw[8 * t + r]
                for c in range(8):
                    rows[8 * ty + r][8 * tx + c] = b >> (7 - c) & 1
        return rows

    def glyph8(self, code: int) -> list[list[int]]:
        raw = self.raw(FONT8 + 16 * (code - 0x100), 16)
        return [[b >> (7 - c) & 1 for c in range(8)] for b in raw]

    # --- names ---
    def name_codes(self, p: int) -> list[int]:
        a, b, c, _ = struct.unpack_from("<4H", self.data, off(NAMES + 8 * p))
        return [a, b] + ([c] if c != 0x200 else [])

    def name(self, p: int) -> str:
        return self.text(self.name_codes(p))

    def reading(self, p: int) -> str:
        return self.text(self.codes_at(0x8C0000 | self.u16(NAMES + 8 * p + 6)))

    # --- persons ---
    def person_raw(self, scenario: int, p: int) -> bytes:
        return self.raw(self.persons_at[scenario] + PERSON_SIZE * p, PERSON_SIZE)

    def person(self, scenario: int, p: int) -> dict:
        return decode_person(self.person_raw(scenario, p))

    def place(self, scenario: int, p: int) -> bytes:
        return self.raw(PLACES[scenario] + PLACE_SIZE * p, PLACE_SIZE)

    # --- countries, factions ---
    def country_name(self, c: int) -> str:
        return self.text([self.u16(COUNTRY_NAMES + 4 * c), self.u16(COUNTRY_NAMES + 4 * c + 2)])

    def country_reading(self, c: int) -> str:
        return self.text(self.codes_at(0x8C0000 | self.u16(COUNTRY_NAMES + 4 * COUNTRY_COUNT + 2 * c)))

    def country_raw(self, scenario: int, c: int) -> bytes:
        return self.raw(COUNTRIES[scenario] + COUNTRY_SIZE * c, COUNTRY_SIZE)

    def country(self, scenario: int, c: int) -> dict:
        return decode_fields(self.country_raw(scenario, c), COUNTRY_FIELDS)

    def gold_food(self, scenario: int, difficulty: int, c: int) -> tuple[int, int]:
        """(金, 米) of country c at the start for a difficulty (0 上級, 1 中級, 2 初級)."""
        if difficulty in DIFFICULTY_GOLD_FOOD:
            a = DIFFICULTY_GOLD_FOOD[difficulty][scenario] + 4 * c
            return self.u16(a), self.u16(a + 2)
        v = self.country(scenario, c)
        return v["金"], v["米"]

    def rulers(self, scenario: int) -> list[int]:
        """Faction f -> ruler person number (0xFF = no faction)."""
        return [self.u8(FACTIONS[scenario] + FACTION_SIZE * f) for f in range(FACTION_COUNT)]

    # --- scenario start state, as the loader $99:E436 builds it ---
    def scenario_wram(self, scenario: int, difficulty: int = 1) -> dict[int, bytes]:
        """WRAM blocks {address: bytes} of persons, countries and factions when the loader returns."""
        countries = bytearray()
        for c in range(COUNTRY_COUNT):
            rec = bytearray(self.country_raw(scenario, c))
            gold, food = self.gold_food(scenario, difficulty, c)
            rec[2:6] = struct.pack("<HH", gold, food)
            countries += rec + b"\0\0"
        countries = countries[:COUNTRY_WRAM_BYTES]
        persons = bytearray()
        for p in range(PERSON_COUNT):
            kind, country = self.place(scenario, p)[:2]
            head = bytearray(7)
            if kind == 0:
                head[1] = country | 0x80
                head[0] = self.country_raw(scenario, country)[0] | 0x80
            persons += head + self.person_raw(scenario, p)
        factions = bytearray()
        for f in range(FACTION_COUNT):
            factions += b"\0" + self.raw(FACTIONS[scenario] + FACTION_SIZE * f, FACTION_SIZE)
        return {PERSON_WRAM: bytes(persons), COUNTRY_WRAM: bytes(countries), FACTION_WRAM: bytes(factions)}

    # --- strategic map ---
    def position(self, c: int) -> tuple[int, int]:
        return self.u8(MAP_POSITIONS + 2 * c), self.u8(MAP_POSITIONS + 2 * c + 1)

    def map_vram(self, forts: list[int] | None = None, persons: bytes | None = None) -> bytes:
        """VRAM 0x0000-0x7FFF of the strategic map ($91:8000): the decompressed, interleaved stream, plus the forts
        (35 砦 bytes, country WRAM +17) and the marching armies (persons = the WRAM person block, 229 x 24); at the
        start of every scenario there are neither."""
        raw = lz(self.data, MAP_STREAM)
        vram = bytearray(len(raw))
        for i in range(0, len(raw), 16):
            vram[i:i + 16:2] = raw[i:i + 8]
            vram[i + 1:i + 16:2] = raw[i + 8:i + 16]
        for c, bits in enumerate(forts or []):
            x, y = self.position(c)
            for b, (dc, dr) in enumerate(MAP_FORT_CELLS):
                if bits >> b & 1:
                    tiles = self.raw(MAP_FORT_TILES + 4 * b, 4)
                    for t, (ec, er) in zip(tiles, ((0, 0), (1, 0), (0, 1), (1, 1))):
                        col, row = 2 * x - 1 + dc + ec, 2 * y - 1 + dr + er
                        vram[2 * (row * MAP_TILES + col)] = t
        for p in range(PERSON_COUNT if persons else 0):
            h = persons[PERSON_WRAM_SIZE * p:PERSON_WRAM_SIZE * p + 3]
            if h[0] & 0xE0 != 0x80 or h[1] == 0xFF or h[1] & 0x80:
                continue
            a, b, c = self.raw(MAP_ARMY_TILES + (6 if h[0] & 0x10 else 0), 3)
            i = 2 * (2 * h[2] * MAP_TILES + 2 * h[1] + (h[2] & 1))
            vram[i], vram[i + 2], vram[i + 256], vram[i + 258] = a, 0xE0 + (h[0] & 15), b, c
        return bytes(vram)

    def map_palette(self) -> list[tuple[int, int, int]]:
        """256 colours: the map's colours 0x20-0x5F (first frame of the colour cycle), the rest black."""
        lo, hi = MAP_COLOURS
        return [(0, 0, 0)] * lo + palette(self.raw(MAP_PALETTE, 2 * (hi - lo))) + [(0, 0, 0)] * (256 - hi)

    def map_image_pixels(self, vram: bytes) -> list[int]:
        """1024 x 1024 colour numbers of a mode-7 VRAM image."""
        tiles = vram[1::2]   # char data: tile t = bytes 64 t .. 64 t + 63
        out = [0] * (1024 * 1024)
        for ty in range(MAP_TILES):
            for tx in range(MAP_TILES):
                t = vram[2 * (ty * MAP_TILES + tx)]
                for y in range(8):
                    o = (8 * ty + y) * 1024 + 8 * tx
                    out[o:o + 8] = tiles[64 * t + 8 * y:64 * t + 8 * y + 8]
        return out

    def marker(self, faction: int) -> tuple[int, int, tuple[int, int, int]]:
        """(OBJ tile, attribute, colour) of a country marker for a faction (0xFF = none)."""
        f = 15 if faction == 0xFF else faction
        colour = palette(self.raw(MAP_MARKER_COLOURS + 32 * (f >> 3) + 2 * (8 + (f & 7)), 2))[0]
        return 0xC8 + (f & 7) + 0x10 * (f >> 3), 0x10 | (6 + (f >> 3)) << 1, colour

    # --- faces ---
    def face_parts(self, p: int) -> bytes:
        return self.raw(FACE_PARTS + 12 * p, 12)

    def face_palette(self, p: int) -> list[tuple[int, int, int]]:
        return palette(self.raw(FACE_PALETTES + 32 * p, 32))

    def face_buffer(self, p: int) -> bytes:
        """The sprite tile buffer $7E:8000-$8FFF as $80:8968 fills it (16 tiles per row, 8 rows, 4bpp)."""
        buf = bytearray(FACE_BUFFER)
        for k, (base, step, size, dests) in enumerate(FACE_SLOTS):
            n = self.face_parts(p)[k]
            if n == 0xFF and k in FACE_OPTIONAL:
                continue
            src = self.raw(base + step * n, size * len(dests))
            for j, d in enumerate(dests):
                buf[d:d + size] = src[size * j:size * j + size]
        return bytes(buf)

    def metasprite(self, i: int) -> list[tuple[int, int, int, int]]:
        p = 0x810000 | self.u16(META_TABLE + 2 * i)
        return [struct.unpack_from("<bbBB", self.data, off(p) + 1 + 4 * k) for k in range(self.u8(p))]

    def face_pixels(self, p: int, frame: int = FACE_META) -> list[int]:
        """48 x 64 colour numbers 0-15 (-1 = transparent), sprites of face metasprite `frame` 0-3 (first = in
        front)."""
        buf = self.face_buffer(p)
        px = [-1] * (FACE_W * FACE_H)
        for dx, dy, t, a in reversed(self.metasprite(FACE_META_BASE.get(p, 0) + frame)):
            hflip, vflip = a >> 6 & 1, a >> 7 & 1
            for ty in range(2):
                for tx in range(2):
                    n = (t & 0xF0) + 16 * ty + ((t + tx) & 15)
                    src = decode_tile4(buf[32 * n:32 * n + 32])
                    for y in range(8):
                        for x in range(8):
                            c = src[8 * y + x]
                            if not c:
                                continue
                            sx = (1 - tx) * 8 + 7 - x if hflip else 8 * tx + x
                            sy = (1 - ty) * 8 + 7 - y if vflip else 8 * ty + y
                            X, Y = FACE_ORIGIN[0] + dx + sx, FACE_ORIGIN[1] + dy + sy
                            if 0 <= X < FACE_W and 0 <= Y < FACE_H:
                                px[Y * FACE_W + X] = c
        return px

    def face_rgb(self, p: int, frame: int = FACE_META) -> list[tuple[int, int, int] | None]:
        pal = self.face_palette(p)
        return [None if c < 0 else pal[c] for c in self.face_pixels(p, frame)]


def decode_person(raw: bytes) -> dict:
    return decode_fields(raw, PERSON_FIELDS)
