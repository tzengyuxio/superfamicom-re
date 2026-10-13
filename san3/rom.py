"""SFC 三國志III (KOEI, 1992) ROM decoding.

Offsets are file offsets of the headerless 1.5 MB HiROM image of the original release (CPU $C0:0000 = file 0).
See docs/ROM_FORMAT.md. Rev 1 keeps the bank $CA tables at the same offsets but moves bank $C1 data and the
compressed-data pointer table, so only the original release is supported.
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Sangokushi III (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

# Compressed data: 491 long pointers ($C7:F3A7) to KOEI LZ streams (tools/koei_lz.py, table block at 0x992F)
DATA_TABLE = 0x7F3A7
DATA_COUNT = 491
LZ_TABLES = 0x992F

# Font: 16x16 1bpp glyphs of 32 bytes (top-left, top-right, bottom-left, bottom-right 8x8 tiles, one byte per
# row). Text code 0x8140 + g is glyph g; glyphs 0-895 at FONT_LOW, 896-1854 at FONT_HIGH. Codes 0x9140+ are
# an escape for codes whose low byte is 0x00: 0x91nn stands for 0x8200 + (nn - 0x40) * 0x100.
FONT_LOW = 0x1000
FONT_HIGH = 0x140000
FONT_SPLIT = 896
GLYPH_COUNT = 1855
TEXT_BASE = 0x8140
TEXT_ESCAPE = 0x9140

SCENARIO_COUNT = 6
SCENARIO_TITLES = 0x7E00B   # 6 long pointers to the titles
SCENARIO_HEADER = 0xAF3A6   # 6 x 33 bytes -> WRAM $2784 ($C7:4671)
HEADER_SIZE = 33

# Persons 0-531 ($CA:8026, sorted by reading): 30 bytes, see Rom.persons()
PERSONS = 0xA8026
PERSON_COUNT = 532
PERSON_SIZE = 30
# Scenario persons ($C7:4BFF via pointer table $C7:E601): 531 x 4 bytes per scenario
SCEN_PERSONS = [0xA4E5E, 0xA56AA, 0xA5EF6, 0xA6742, 0xA6F8E, 0xA77DA]
SCEN_PERSON_COUNT = 531
# Provinces 1-46 names: 25 bytes = 2 bytes, name (7), reading (8 half-width katakana), 4 LE16
PROVINCE_NAMES = 0xADEDE
PROVINCE_COUNT = 46
PROVINCE_NAME_SIZE = 25
# Scenario provinces ($C7:4C19 via $C7:E613): 46 x 30 bytes per scenario
SCEN_PROVINCES = [0xABE7E, 0xAC3E2, 0xAC946, 0xACEAA, 0xAD40E, 0xAD972]
SCEN_PROVINCE_SIZE = 30
# Scenario factions ($C7:4DA4 via $C7:E625): 21 x 25 bytes per scenario
SCEN_FACTIONS = [0xAE354, 0xAE561, 0xAE76E, 0xAE97B, 0xAEB88, 0xAED95]
FACTION_COUNT = 21
FACTION_SIZE = 25
# 22 x 6 bytes [i * 6 + scenario] -> WRAM $308D ($C7:4E80), meaning unknown
SCEN_EXTRA = 0xAEFA2
SCEN_EXTRA_COUNT = 22
# Items: 13 x 18 bytes (5 bytes + name); owners [item * 6 + scenario] LE16 person ($C7:4ED9)
ITEMS = 0xAF2BC
ITEM_COUNT = 13
ITEM_SIZE = 18
ITEM_OWNERS = 0xAF220
NONE16 = 0xFFFF

RANK_LABELS = 0x1C8FD       # 7 long pointers: 君主 軍師 将軍 武官 文官 在野 太守
UNIT_LABELS = 0x1C935       # 7 long pointers: 歩兵 騎馬 弩 強弩 闘艦 蒙衝 走舸

# Faces: 40x48 = 5x6 4bpp tiles, row-major. Face word of a person ($C1:65D7):
#   1..307 plain face: data entry FACE_ENTRY + n (960 bytes)
#   bit 15 set: composite face built from 5 tile parts ($C1:6477)
# shown with palette FACE_PALETTE (BG palette 4 on the profile screen)
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
FACE_ENTRY = 153
FACE_COUNT = 307
FACE_PALETTE = 0x1C187
# Composite faces: type t (0-12) from the face word, then for each part p (0-4) a variant
PART_SOURCES = 0x1E859      # [t][p] long pointer to the part's uncompressed 4bpp tiles
PART_SIZE = 0x1C326         # [t][p] LE16: p < 3: width * 10 + height; p >= 3: tiles per variant
PART_POS = 0x1C3A8          # [t][p] LE16: x * 10 + y of the part on the 5x6 grid
PART3_RECTS = 0x1C42A       # [t] 6 LE16: count, then rectangles as decimal digits x y w h (part 3)
PART4_RECTS = 0x1C4C6       # [t] 4 LE16: same for part 4
TYPE_TABLE = (0x1C538, 0x1C52E)  # LE16 by face & 7, for bit 14 = 0 / 1 (the latter + 8)
COMPOSITE_TYPES = 13
PART_VARIANTS = (6, 2, 4, 4, 4)  # variants stored per part (the face word has room for 8, 2, 4, 4, 4)

# Big map: one screen of 30 x 28 BG tiles (BG2, tilemap VRAM word $1400 from column 1). The tilemap is stored
# uncompressed; its tiles are data entry MAP_CHR loaded at tile MAP_CHR_TILE, BG palette 2 = MAP_PALETTE.
# Each province k gets a marker tile at MAP_CELLS[k] = (x - 1, y) ($C1:5C7F): tile 0x370 + colour from
# entry MARKER_CHR (palette 3 = MARKER_PALETTE); colour = scenario header +4 + faction, 0x19 if no faction.
MAP_TILEMAP = 0x2E1AC
MAP_W, MAP_H = 30, 28
MAP_CHR, MAP_CHR_TILE = 461, 0x80
MARKER_CHR, MARKER_TILE = 465, 0x370
MAP_PALETTE, MARKER_PALETTE = 0x1C067, 0x1C167
MAP_PALETTE_FRAMES = (0x1C067, 0x1C087)  # colour-cycle frames of palette 2 (water: colours 3 and 11 cycle)
MAP_CELLS = 0x1D0CF
MARKER_NONE = 0x19

# Tactical maps: data entry TACTICAL_ENTRY + k is the battlefield of province index k (loaded to WRAM $7E:C104).
# 1342 bytes = layer A 22 x 21 (graphic/cell code, read by $C3:56BE), layer B 22 x 20 and layer C 22 x 20.
TACTICAL_ENTRY = 47
TACTICAL_W = 22
TACTICAL_LAYERS = ((0, 21), (462, 20), (902, 20))  # (offset, rows)


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
            name = next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc")))
            data = z.read(name)
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]  # drop a 512-byte copier header if present


def load_charset(path: str = CHARSET) -> str:
    with open(path, encoding="utf-8") as f:
        cs = "".join(line.rstrip("\n") for line in f if not line.startswith("#"))
    assert len(cs) == GLYPH_COUNT, len(cs)
    return cs


def digits(v: int) -> tuple[int, int, int, int]:
    """Decimal digits (thousands, hundreds, tens, ones) as $C1:5EAF takes them apart."""
    return v // 1000 % 10, v // 100 % 10, v // 10 % 10, v % 10


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.charset = load_charset()
        self._cache: dict[int, bytes] = {}

    def ptr(self, at: int) -> int:
        return hirom(int.from_bytes(self.data[at:at + 3], "little"))

    def entry(self, i: int) -> bytes:
        """Decompressed data entry i."""
        if i not in self._cache:
            self._cache[i] = koei_lz.decompress(self.data, self.ptr(DATA_TABLE + 3 * i), LZ_TABLES)[0]
        return self._cache[i]

    # --- text ---

    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g."""
        a = FONT_LOW + 32 * g if g < FONT_SPLIT else FONT_HIGH + 32 * (g - FONT_SPLIT)
        raw = self.data[a:a + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    def char(self, code: int) -> str:
        if code >= TEXT_ESCAPE:
            code = 0x8200 + ((code - TEXT_ESCAPE) << 8)
        g = code - TEXT_BASE
        return self.charset[g] if 0 <= g < GLYPH_COUNT else "　"

    def text(self, raw: bytes) -> str:
        """Game text -> str: 2-byte codes through the charset, half-width katakana and ASCII as cp932,
        0A newline, ESC 'C' n (colour) dropped, 00 ends."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            c = raw[i]
            if (0x81 <= c < 0xA0 or c >= 0xE0) and i + 1 < len(raw):
                out.append(self.char(c << 8 | raw[i + 1]))
                i += 2
            elif c == 0x1B:
                i += 3
            else:
                out.append("\n" if c == 0x0A else bytes([c]).decode("cp932", "replace"))
                i += 1
        return "".join(out)

    def labels(self, table: int, n: int) -> list[str]:
        return [self.text(self.data[self.ptr(table + 3 * i):self.ptr(table + 3 * i) + 40]) for i in range(n)]

    def scenario_titles(self) -> list[str]:
        return self.labels(SCENARIO_TITLES, SCENARIO_COUNT)

    def rank_labels(self) -> list[str]:
        return self.labels(RANK_LABELS, 7)

    def unit_labels(self) -> list[str]:
        return self.labels(UNIT_LABELS, 7)

    # --- static tables ---

    def persons(self) -> list[dict]:
        """+0 face LE16, +2 野心<<6 | 運<<4 | 冷静<<2 | 勇猛, +3 ?, +4 flags?, +5 陸指, +6 水指, +7 武力,
        +8 智力, +9 政治, +10 魅力, +11 相性, +12 義理, +13 血縁 (FF none), +14 生年 (AD),
        +15 name (3 codes BE, 0-padded), +22 reading (8 half-width katakana)."""
        out = []
        for pid in range(PERSON_COUNT):
            o = PERSONS + PERSON_SIZE * pid
            r = self.data[o:o + PERSON_SIZE]
            out.append({
                "id": pid, "offset": o, "raw": r, "face": le16(r, 0),
                "ambition": r[2] >> 6, "luck": r[2] >> 4 & 3, "calm": r[2] >> 2 & 3, "bravery": r[2] & 3,
                "unknown3": r[3], "flags4": r[4], "land": r[5], "water": r[6], "war": r[7], "int": r[8],
                "pol": r[9], "cha": r[10], "affinity": r[11], "duty": r[12], "kin": r[13], "born": r[14],
                "name": self.text(r[15:22]), "reading": r[22:30].rstrip(b"\0").decode("cp932"),
            })
        return out

    def provinces(self) -> list[dict]:
        """Province names; id 1-46 (scenario tables are 0-based: index id - 1)."""
        out = []
        for k in range(PROVINCE_COUNT):
            o = PROVINCE_NAMES + PROVINCE_NAME_SIZE * k
            r = self.data[o:o + PROVINCE_NAME_SIZE]
            out.append({"id": k + 1, "offset": o, "b0": r[0], "b1": r[1], "name": self.text(r[2:9]),
                        "reading": r[9:17].rstrip(b"\0").decode("cp932"),
                        "words": [le16(r, 17 + 2 * i) for i in range(4)]})
        return out

    def items(self) -> list[dict]:
        """+0 kind (0 書, 1 剣/矛, 2 馬, 3 青嚢書, 4 玉璽), +1, +2, +3 能力加算 (推測), +4, +5 name."""
        out = []
        for i in range(ITEM_COUNT):
            o = ITEMS + ITEM_SIZE * i
            r = self.data[o:o + ITEM_SIZE]
            out.append({"id": i, "kind": r[0], "b1": r[1], "b2": r[2], "bonus": r[3], "b4": r[4],
                        "name": self.text(r[5:18]),
                        "owners": [le16(self.data, ITEM_OWNERS + 12 * i + 2 * sc) for sc in range(SCENARIO_COUNT)]})
        return out

    # --- scenarios ---

    def scenario_header(self, sc: int) -> dict:
        """+0 LE16 start year - 1, +2 ?, +3 number of factions, +4..21 faction order, +22..32 ?"""
        r = self.data[SCENARIO_HEADER + HEADER_SIZE * sc:SCENARIO_HEADER + HEADER_SIZE * (sc + 1)]
        return {"raw": r, "year": le16(r, 0) + 1, "factions": r[3], "order": list(r[4:4 + r[3]])}

    def scenario_persons(self, sc: int) -> list[dict]:
        """4 bytes per person: 兵士 / 100 (FF: none), rank (bit 7 flag, low 7 bits: 0 君主 1 軍師 2 将軍
        3 武官 4 文官 5 在野 6 太守?; FF: not in play), 忠誠, province (0-based, FF none)."""
        base = SCEN_PERSONS[sc]
        out = []
        for pid in range(SCEN_PERSON_COUNT):
            r = self.data[base + 4 * pid:base + 4 * pid + 4]
            out.append({"id": pid, "raw": r, "soldiers": r[0] * 100, "rank_byte": r[1], "rank": r[1] & 0x7F,
                        "rank_flag": r[1] >> 7, "loyalty": r[2], "province": r[3]})
        return out

    def scenario_provinces(self, sc: int) -> list[dict]:
        """30 bytes per province (index 0-45), copied to WRAM $27BF + 49 * k by $C7:4C19."""
        base = SCEN_PROVINCES[sc]
        out = []
        for k in range(PROVINCE_COUNT):
            r = self.data[base + SCEN_PROVINCE_SIZE * k:base + SCEN_PROVINCE_SIZE * (k + 1)]
            out.append({
                "id": k, "raw": r, "next": r[0], "w1": le16(r, 1), "population": le16(r, 3) * 10000,
                "gold": le16(r, 5) * 100, "food": le16(r, 7) * 100, "b9": r[9], "b10": r[10], "b11": r[11],
                "develop": r[12], "b13": r[13], "flood": r[14], "commerce": le16(r, 15), "tax": r[17],
                "loyalty": r[18], "w19": le16(r, 19), "w21": le16(r, 21), "w23": le16(r, 23),
                "b25": r[25], "b26": r[26], "b27": r[27], "training": r[28], "morale": r[29],
            })
        return out

    def scenario_factions(self, sc: int) -> list[dict]:
        """25 bytes per faction slot: +0 LE16 ruler (FFFF = empty slot), +2 capital province (0-based),
        +3 ?, +4..24 21 bytes (one per faction slot, 推測: relations)."""
        base = SCEN_FACTIONS[sc]
        out = []
        for k in range(FACTION_COUNT):
            r = self.data[base + FACTION_SIZE * k:base + FACTION_SIZE * (k + 1)]
            out.append({"id": k, "raw": r, "ruler": le16(r, 0), "capital": r[2], "b3": r[3], "rel": list(r[4:25])})
        return out

    def scenario_extra(self, sc: int) -> list[int]:
        return [self.data[SCEN_EXTRA + 6 * i + sc] for i in range(SCEN_EXTRA_COUNT)]

    # --- faces ---

    def face_palette(self) -> list[int]:
        return [le16(self.data, FACE_PALETTE + 2 * i) for i in range(16)]

    def composite_type(self, face: int) -> int:
        hi = face >> 14 & 1
        return le16(self.data, TYPE_TABLE[hi] + 2 * (face & 7)) + 8 * hi

    def composite_variants(self, face: int) -> list[int]:
        """Variant of parts 0-4 ($C1:5ED9 cases 0-4)."""
        return [face >> 7 & 7, face >> 10 & 1, face >> 11 & 3, face >> 3 & 3, face >> 5 & 3]

    def composite_rects(self, t: int, p: int) -> list[tuple[int, int, int, int]]:
        """Tile rectangles (x, y, w, h) on the 5x6 grid that part p of type t fills, in source order."""
        d = self.data
        pos = le16(d, PART_POS + 10 * t + 2 * p)
        ox, oy = pos // 10, pos % 10
        if p < 3:
            size = le16(d, PART_SIZE + 10 * t + 2 * p)
            return [(ox, oy, size // 10, size % 10)]
        table = PART3_RECTS + 12 * t if p == 3 else PART4_RECTS + 8 * t
        out = []
        for k in range(1, le16(d, table) + 1):
            x, y, w, h = digits(le16(d, table + 2 * k))
            out.append((ox + x, oy + y, w, h))
        return out

    def face_tiles(self, face: int) -> bytes:
        """960 bytes: the 30 tiles of a face as the game puts them in VRAM."""
        if face == NONE16:
            raise ValueError("random face")
        if not face & 0x8000:
            if face == 0 or face > FACE_COUNT:
                face = 1
            return self.entry(FACE_ENTRY + face)[:FACE_BYTES]
        t = self.composite_type(face)
        out = bytearray(FACE_BYTES)
        for p, v in enumerate(self.composite_variants(face)):
            for cell, raw in self.composite_part(t, p, v):
                out[32 * cell:32 * cell + 32] = raw
        return bytes(out)

    def composite_part(self, t: int, p: int, v: int) -> list[tuple[int, bytes]]:
        """(cell 0-29, 32-byte tile) of variant v of part p of type t: the part's tiles are stored uncompressed,
        variant after variant, row by row through its rectangles ($C1:6058)."""
        rects = self.composite_rects(t, p)
        ntiles = sum(w * h for _, _, w, h in rects)
        src = self.ptr(PART_SOURCES + 15 * t + 3 * p) + 32 * ntiles * v
        out = []
        for x, y, w, h in rects:
            for row in range(h):
                for col in range(w):
                    out.append((FACE_W * (y + row) + x + col, self.data[src:src + 32]))
                    src += 32
        return out

    def face_pixels(self, face: int) -> list[int]:
        """40x48 colour numbers, row-major."""
        tiles = self.face_tiles(face)
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, face: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(face)]

    # --- maps ---

    def palette(self, at: int) -> list[int]:
        return [le16(self.data, at + 2 * i) for i in range(16)]

    def map_cells(self) -> list[tuple[int, int]]:
        """Marker cell (column, row) of province index k on the MAP_W x MAP_H map."""
        return [(self.data[MAP_CELLS + 2 * k], self.data[MAP_CELLS + 2 * k + 1]) for k in range(PROVINCE_COUNT)]

    def province_factions(self, sc: int) -> dict[int, int]:
        """Province index -> faction slot at the start of scenario sc (each faction's chain from its capital)."""
        provs = self.scenario_provinces(sc)
        out = {}
        for fa in self.scenario_factions(sc):
            k, seen = fa["capital"], 0
            while fa["ruler"] != NONE16 and k != 0xFF and seen < PROVINCE_COUNT:
                out[k] = fa["id"]
                k, seen = provs[k]["next"], seen + 1
        return out

    def map_tilemap(self, sc: int | None = None) -> list[int]:
        """MAP_W x MAP_H BG tilemap entries, row-major; with sc, the province markers of that scenario's start."""
        tm = [le16(self.data, MAP_TILEMAP + 2 * i) for i in range(MAP_W * MAP_H)]
        if sc is not None:
            header = self.scenario_header(sc)["raw"]
            pf = self.province_factions(sc)
            for k, (x, y) in enumerate(self.map_cells()):
                colour = header[4 + pf[k]] if k in pf else MARKER_NONE
                tm[y * MAP_W + x] = 0x0C00 | (MARKER_TILE + colour)
        return tm

    def map_rgb(self, sc: int | None = None) -> list[tuple[int, int, int]]:
        """(MAP_W * 8) x (MAP_H * 8) pixels of the big map."""
        chr_map, chr_marker = self.entry(MAP_CHR), self.entry(MARKER_CHR)
        pals = {2: self.palette(MAP_PALETTE), 3: self.palette(MARKER_PALETTE)}
        w = MAP_W * 8
        out = [(0, 0, 0)] * (w * MAP_H * 8)
        for i, e in enumerate(self.map_tilemap(sc)):
            t, pal = e & 0x3FF, [bgr555_rgb(c) for c in pals.get(e >> 10 & 7, pals[2])]
            if t >= MARKER_TILE:
                raw = chr_marker[32 * (t - MARKER_TILE):32 * (t - MARKER_TILE + 1)]
            else:
                raw = chr_map[32 * (t - MAP_CHR_TILE):32 * (t - MAP_CHR_TILE + 1)]
            px = decode_tile(raw) if len(raw) == 32 else [0] * 64
            for j, c in enumerate(px):
                x, y = j % 8, j // 8
                if e & 0x4000:
                    x = 7 - x
                if e & 0x8000:
                    y = 7 - y
                out[(i // MAP_W * 8 + y) * w + i % MAP_W * 8 + x] = pal[c]
        return out

    def tactical_map(self, k: int) -> list[list[list[int]]]:
        """Battlefield of province index k: [layer A, layer B, layer C], each a list of rows of TACTICAL_W."""
        d = self.entry(TACTICAL_ENTRY + k)
        return [[list(d[o + TACTICAL_W * y:o + TACTICAL_W * (y + 1)]) for y in range(rows)] for o, rows in TACTICAL_LAYERS]
