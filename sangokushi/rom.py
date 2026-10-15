"""SFC スーパー三國志 (KOEI) ROM decoding.

Offsets are file offsets of the headerless 1 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
The LZ decompressor is the shared one in tools/koei_lz.py ($C0:F194). The program is compiled C: routines take
their arguments on the stack; text goes through a printf at $C2:16DC.
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Super Sangokushi (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

LZ_TABLES = 0xF037                       # decoder lookup tables (koei_lz.find_tables)
ENTRIES, ENTRY_COUNT = 0xED802, 817      # 3-byte pointers to LZ streams ("entries"); entries 0 and 186 are raw

# Font: glyph g = 16x16 1bpp, 32 bytes at FONT + 32 g (8x8 tiles TL TR BL BR, one byte per row).
# Text code 0x8140 + g, big-endian; 0x9140 + k stands for 0x8200 + 0x100 k (low byte 00 cannot be stored).
FONT, GLYPH_COUNT = 0x87BF3, 921

# Name table: 256 x 18 bytes: reading (8 bytes, one-byte katakana, NUL padded), 3 kanji codes (BE16, 0 = none),
# 0, face code, birth year (BE16). Person p of the records below is name p; p = 0 is a second 曹操 (face 3,
# lower stats) that the game does not list (purpose unsolved).
NAMES, NAME_SIZE, PERSON_COUNT = 0x5C314, 18, 256

# New game: three blocks are copied from ROM to WRAM, then scenarios 2-5 patch some fields ($00:1772 is the
# MVN helper that does it). Person record p is at WRAM PERSON_WRAM + 18 p; the copy starts at its byte +1.
COUNTRY_INIT, COUNTRY_WRAM, COUNTRY_COUNT, COUNTRY_SIZE = 0xFA129, 0x2052, 58, 30
FACTION_INIT, FACTION_WRAM, FACTION_COUNT, FACTION_SIZE = 0xFA7F5, 0x2722, 14, 77
PERSON_INIT, PERSON_WRAM, PERSON_SIZE = 0xFAC2A, 0x2B57, 18
PERSON_COPY = (0xFAC2B, 0x2B58, 0x1200)  # (ROM, WRAM, length) of the person block copy
# Scenario 2-5 patches: 12 bytes per record = 4 scenarios x 3 bytes (scenario s uses bytes 3 (s - 2)..)
COUNTRY_PATCH = 0xFE9AE                  # -> country +13..+15
FACTION_PATCH = 0xFEC66                  # -> faction +0..+2
PERSON_PATCH = 0xFED0E                   # person p = 1..255 at + 12 (p - 1) -> person +7, +10, +11
SCENARIO_COUNT = 5
SCENARIO_LIST = 0x3F679                  # 5 x 3-byte pointers: "1 董卓打倒     189年" (the scenario list lines)
SCENARIO_NAMES = 0x3F8D0                 # 5 x 3-byte pointers: the names alone
PERSON_STATS = ["身体", "知力", "武力", "カリスマ", "運勢"]  # person record +1..+5

# Countries (static): 58 x 15 bytes: state, flags (unsolved), 9 neighbour countries (0 = none), x, y (LE16,
# unsolved: not the label position on the map). States: 15 x 13 bytes: reading (8), 2 kanji codes, 0.
COUNTRY_TABLE, COUNTRY_TABLE_SIZE = 0xEE249, 15
STATES, STATE_SIZE, STATE_COUNT = 0xEE5AF, 13, 15

# Faces: 40x48 = 5x6 4bpp tiles row-major (960 bytes), loaded by $C1:143F(code).
# code < 0x80: portrait = LZ entry PORTRAIT_ENTRY + code. 0x80-0xFE: composite (male, 6 types); 0xFF-0x132:
# composite (female, 2 types). A composite record is 6 bytes (5 part numbers, type); part k of type t is the LZ
# stream at the 3-byte pointer parts + 75 t + 3 (first[k] + part), written at tile (x, y) of the position table.
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
PORTRAIT_ENTRY, PORTRAIT_COUNT = 303, 128
FACE_PALETTE = 0x4E711                   # OBJ palette 1 (CGRAM 0x120): a face is 30 sprites, tiles 0x164-0x181
FACE_OAM_TILE, FACE_CGRAM = 0x164, 0x120  # (8x8 sprites, VRAM 0xC000 + 32 tile = 0xEC80)
COMPOSITES = {  # kind: (first code, count, records, parts, first part per slot, positions, types)
    "male": (0x80, 127, 0xAEA6, 0xEDE29, 0xEE23F, 0xEE1BD, 6),
    "female": (0xFF, 52, 0xB1A0, 0xEDFEB, 0xEE235, 0xEE195, 2),
}
FACE_SLOTS = 5
LAST_FACE = 0xFF + 52 - 1

# Strategic map: 30 x 22 BG tilemap words at MAP_TILEMAP (BG1, VRAM 0x9800 from column 1 row 1); tile n >= 1 is
# 4bpp tile n - 1 of the LZ stream at MAP_TILES (character base VRAM 0xA000). MAP_MASK is the BG2 overlay that
# is coloured by owner (30 x 22 tiles, value 1 inside the land, 0 on borders / sea). The game copies 23 rows;
# the 23rd (palette 3) lies under the message window and is not part of the map.
MAP_TILES, MAP_TILEMAP, MAP_W, MAP_H = 0x2C00, 0xC426, 30, 22
MAP_MASK = 0x74D7
MAP_PALETTE_FRAMES = 0x4EA91             # BG palette 2: 10 frames x 32 bytes, the sea colours cycle
MAP_PALETTE_STILL = 4                    # frame 4 has all sea colours equal
# The mask has 58 separate regions (4-connected pixels of value 1), one per country. When the map is set up the
# game paints region c with colour owner(c) + 1 (BG2 palette 3 = MAP_OWNER_PALETTE; 1 = no owner). Which region is
# which country was found by experiment (verify_maps.py); how the game itself finds them is unsolved. Region of
# country c = the one holding pixel MAP_REGION_SEEDS[c - 1] (its first pixel in raster order).
MAP_REGION_SEEDS = [
    (212, 5), (198, 21), (172, 25), (152, 34), (147, 43), (180, 41), (155, 49), (207, 40), (187, 44), (194, 53),
    (213, 60), (176, 51), (156, 65), (102, 27), (90, 24), (135, 36), (111, 41), (126, 47), (99, 50), (140, 57),
    (92, 48), (77, 51), (82, 69), (69, 37), (44, 47), (49, 31), (25, 17), (203, 71), (189, 69), (161, 79),
    (224, 83), (172, 87), (148, 92), (163, 98), (181, 99), (145, 112), (121, 71), (113, 71), (122, 88), (112, 87),
    (127, 100), (113, 99), (134, 115), (106, 112), (90, 71), (83, 87), (72, 82), (34, 80), (52, 97), (25, 99),
    (62, 108), (33, 112), (42, 122), (6, 114), (71, 117), (179, 127), (125, 128), (48, 136),
]
MAP_OWNER_PALETTE = 0x4E851

# Battle fields: country c -> grid = LZ entry BATTLE_GRID + c - 1 (14 x 12 cells, terrain << 3 | zone),
# BG2 tilemap = LZ entry BATTLE_TILEMAP + c - 1 (28 x 25 words: a cell is 2 x 2 tiles, odd columns one tile
# lower). Characters: LZ entry BATTLE_CHR at tile 0x60 (VRAM 0x4C00, character base 0x4000).
BATTLE_TILEMAP, BATTLE_GRID, BATTLE_CHR, BATTLE_CHR_FIRST = 187, 245, 431, 0x60
BATTLE_COLS, BATTLE_ROWS, BATTLE_TW, BATTLE_TH = 14, 12, 28, 25
BATTLE_PALETTES = {5: 0x4E771, 6: 0x4E791, 7: 0x4E7B1}
BATTLE_PALETTE7_FRAMES = 3               # palette 7 cycles through 0x4E7B1 + 32 k, k = 0..2 (colours 7-15 move)
TERRAIN = ["平地", "山", "森林", "河", "城", "雪山"]  # names as in the FC notes (looked at, not from the game)
# The ROM grids have no castle cells (terrain 4). Castles: 58 x 10 bytes at CASTLES, (column + 1) << 4 | (row + 1)
# per castle place, FF = none. When the battle starts ($C3:836F) the game ORs terrain 4 into the first n places,
# n = the country's 城 (+18 low 4 bits), and draws the 2 x 2 castle tiles CASTLE_TILES there. The other places
# are presumably where 築城 adds castles (not checked).
CASTLES, CASTLE_SLOTS, CASTLE_TERRAIN = 0x2EED2, 10, 4
CASTLE_TILES = [0x15A4, 0x15A5, 0x15A6, 0x15A7]
BATTLE_TARGET_WRAM = 0x2720              # WRAM word: the attacked country's record (COUNTRY_WRAM + 30 (c - 1))


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


def be16(raw: bytes, i: int) -> int:
    return raw[i] << 8 | raw[i + 1]


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


def code_glyph(code: int) -> int:
    """Font glyph of a two-byte text code (escape 0x9140 + k = 0x8200 + 0x100 k); -1 if outside the font."""
    if code >= 0x9140:
        code = 0x8200 + ((code - 0x9140) << 8)
    g = code - 0x8140
    return g if 0 <= g < GLYPH_COUNT else -1


def encode_glyph(g: int) -> bytes:
    """Text code of font glyph g (with the 0x9140 + k escape for low byte 00)."""
    code = 0x8140 + g
    if code & 0xFF == 0:
        code = 0x9140 + ((code - 0x8200) >> 8)
    return code.to_bytes(2, "big")


def face_kind(code: int) -> str:
    if code < PORTRAIT_COUNT:
        return "portrait"
    return "male" if code < COMPOSITES["female"][0] else "female"


def tiles_rgb(tilemap: list[int], w: int, h: int, chr_: bytes, first: int, pals: dict) -> list:
    """RGB list (w*8 x h*8) of a BG tilemap: tile n is chr_[32 (n - first)..]; entries whose palette is missing
    from pals or whose tile is outside chr_ are drawn black."""
    out: list = [(0, 0, 0)] * (w * 8 * h * 8)
    cache: dict[int, list[int]] = {}
    for i, e in enumerate(tilemap):
        n, pal = (e & 0x3FF) - first, pals.get(e >> 10 & 7)
        if pal is None or not 0 <= n < len(chr_) // 32:
            continue
        if n not in cache:
            cache[n] = decode_tile(chr_[32 * n:32 * n + 32])
        px = cache[n]
        ox, oy = i % w * 8, i // w * 8
        for k, v in enumerate(px):
            y, x = divmod(k, 8)
            if e & 0x4000:
                x = 7 - x
            if e & 0x8000:
                y = 7 - y
            out[(oy + y) * w * 8 + ox + x] = pal[v]
    return out


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        assert koei_lz.find_tables(self.data) == LZ_TABLES
        self.charset = load_charset()
        self._lz: dict[int, bytes] = {}

    # ------------------------------------------------------------ generic
    def lz(self, offset: int) -> bytes:
        if offset not in self._lz:
            self._lz[offset] = koei_lz.decompress(self.data, offset, LZ_TABLES)[0]
        return self._lz[offset]

    def p24(self, o: int) -> int:
        return int.from_bytes(self.data[o:o + 3], "little") & 0x3FFFFF

    def entry(self, i: int) -> bytes:
        """Decompressed LZ entry i of the pointer table at ENTRIES."""
        return self.lz(self.p24(ENTRIES + 3 * i))

    def palette(self, o: int) -> list[int]:
        return [le16(self.data, o + 2 * i) for i in range(16)]

    def palette_rgb(self, o: int) -> list[tuple[int, int, int]]:
        return [bgr555_rgb(c) for c in self.palette(o)]

    # ------------------------------------------------------------ text
    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g."""
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    def text(self, raw: bytes) -> str:
        """Game string -> str (stops at NUL). 0x81-0x84 / 0x91 lead bytes are font codes; 0xA1-0xDF one-byte
        katakana (kept half-width); 0x1B + one byte is a display escape (colour, kana style) and is dropped;
        0x20-0x7E ASCII (spaces, printf formats); other bytes become [xx]."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            c = raw[i]
            if (0x81 <= c <= 0x84 or c == 0x91) and i + 1 < len(raw):
                code = c << 8 | raw[i + 1]
                g = code_glyph(code)
                out.append(self.charset[g] if g >= 0 else f"[{code:04x}]")
                i += 2
            elif 0xA1 <= c <= 0xDF:
                out.append(bytes([c]).decode("cp932"))
                i += 1
            elif c == 0x1B:
                i += 2 if i + 1 < len(raw) and raw[i + 1] != 0x43 else 3  # 1B 43 n: colour n
            else:
                out.append(chr(c) if 0x20 <= c < 0x7F else f"[{c:02x}]")
                i += 1
        return "".join(out)

    def cstring(self, p: int) -> str:
        return self.text(self.data[p:self.data.index(b"\0", p) + 1])

    def glyph_codes(self, raw: bytes) -> list[int]:
        """Font glyphs of the two-byte codes of a string (up to NUL; one-byte codes skipped)."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            if 0x81 <= raw[i] <= 0x84 or raw[i] == 0x91:
                out.append(code_glyph(be16(raw, i)))
                i += 2
            else:
                i += 1
        return out

    def kanji(self, codes: list[int]) -> str:
        return "".join(self.charset[code_glyph(c)] for c in codes if c)

    # ------------------------------------------------------------ names and persons
    def name_record(self, p: int) -> bytes:
        return self.data[NAMES + NAME_SIZE * p:NAMES + NAME_SIZE * (p + 1)]

    def names(self) -> list[dict]:
        """256 name entries: id, name (kanji), reading (half-width katakana), face code, birth year."""
        out = []
        for p in range(PERSON_COUNT):
            r = self.name_record(p)
            out.append({"id": p, "name": self.kanji([be16(r, 8 + 2 * k) for k in range(3)]),
                        "reading": self.text(r[0:8]), "face": r[15], "born": be16(r, 16),
                        "name_codes": [be16(r, 8 + 2 * k) for k in range(3)], "byte14": r[14]})
        return out

    def scenarios(self) -> list[dict]:
        """id 1-5, name, start year (from the scenario list line)."""
        out = []
        for k in range(SCENARIO_COUNT):
            line = self.cstring(self.p24(SCENARIO_LIST + 3 * k))
            out.append({"id": k + 1, "name": self.cstring(self.p24(SCENARIO_NAMES + 3 * k)),
                        "year": int(line.rstrip("年").split()[-1])})
        return out

    def scenario_wram(self, sc: int) -> bytearray:
        """The new-game WRAM (bank $7E, 128 KB) as far as the scenario blocks go: base copies, then patches."""
        w = bytearray(0x20000)
        d = self.data
        w[COUNTRY_WRAM:COUNTRY_WRAM + COUNTRY_COUNT * COUNTRY_SIZE] = \
            d[COUNTRY_INIT:COUNTRY_INIT + COUNTRY_COUNT * COUNTRY_SIZE]
        w[FACTION_WRAM:FACTION_WRAM + FACTION_COUNT * FACTION_SIZE] = \
            d[FACTION_INIT:FACTION_INIT + FACTION_COUNT * FACTION_SIZE]
        src, dst, n = PERSON_COPY
        w[dst:dst + n] = d[src:src + n]
        if sc > 1:
            k = 3 * (sc - 2)
            for c in range(COUNTRY_COUNT):
                o = COUNTRY_WRAM + COUNTRY_SIZE * c + 13
                w[o:o + 3] = d[COUNTRY_PATCH + 12 * c + k:COUNTRY_PATCH + 12 * c + k + 3]
            for f in range(FACTION_COUNT):
                o = FACTION_WRAM + FACTION_SIZE * f
                w[o:o + 3] = d[FACTION_PATCH + 12 * f + k:FACTION_PATCH + 12 * f + k + 3]
            for p in range(1, PERSON_COUNT):
                s = PERSON_PATCH + 12 * (p - 1) + k
                o = PERSON_WRAM + PERSON_SIZE * p
                w[o + 7] = d[s]
                w[o + 10:o + 12] = d[s + 1:s + 3]
        return w

    def persons(self, sc: int = 1, wram: bytes | None = None) -> list[dict]:
        """Person records of scenario sc (or of a WRAM image of bank $7E) joined with the name table (p = 0..255)."""
        w = self.scenario_wram(sc) if wram is None else wram
        year = self.scenarios()[sc - 1]["year"]
        out = []
        for n in self.names():
            p = n["id"]
            r = w[PERSON_WRAM + PERSON_SIZE * p:PERSON_WRAM + PERSON_SIZE * (p + 1)]
            rec = dict(n)
            rec.update({"age": year - n["born"], "stats": list(r[1:6]), "loyalty": r[6], "flags": r[7],
                        "navy": r[7] & 1, "troops": le16(r, 8), "country": r[10], "faction": r[11],
                        "morale": r[12], "arms": r[13], "training": r[14],
                        "raw": bytes(r)})
            out.append(rec)
        return out

    # ------------------------------------------------------------ scenarios: countries and factions
    def countries(self, sc: int = 1, wram: bytes | None = None) -> list[dict]:
        """58 countries (number 1-58) of scenario sc (or of a WRAM image) with the static table and the state."""
        w = self.scenario_wram(sc) if wram is None else wram
        states = self.states()
        out = []
        for c in range(COUNTRY_COUNT):
            r = w[COUNTRY_WRAM + COUNTRY_SIZE * c:COUNTRY_WRAM + COUNTRY_SIZE * (c + 1)]
            t = self.data[COUNTRY_TABLE + COUNTRY_TABLE_SIZE * c:COUNTRY_TABLE + COUNTRY_TABLE_SIZE * (c + 1)]
            out.append({"id": c + 1, "state": t[0], "state_name": states[t[0]]["name"], "flags": t[1],
                        "neighbours": [x for x in t[2:11] if x], "x": le16(t, 11), "y": le16(t, 13),
                        "w0": le16(r, 0), "gold": le16(r, 2), "food": le16(r, 4), "land": r[6], "flood": 100 - r[7],
                        "control": r[7], "population": le16(r, 8), "loyalty": r[10], "horses": r[11], "iron": r[12],
                        "b13": r[13], "owner": r[14], "governor": r[15], "b16": r[16], "b17": r[17],
                        "castle": r[18] & 15, "b18": r[18] >> 4, "b19": r[19], "raw": bytes(r)})
        return out

    def states(self) -> list[dict]:
        out = []
        for s in range(STATE_COUNT):
            r = self.data[STATES + STATE_SIZE * s:STATES + STATE_SIZE * (s + 1)]
            out.append({"id": s, "name": self.kanji([be16(r, 8), be16(r, 10)]), "reading": self.text(r[0:8])})
        return out

    def factions(self, sc: int = 1, wram: bytes | None = None) -> list[dict]:
        """14 faction records (number f + 1 is what persons +11 and countries +14 hold)."""
        w = self.scenario_wram(sc) if wram is None else wram
        out = []
        for f in range(FACTION_COUNT):
            r = w[FACTION_WRAM + FACTION_SIZE * f:FACTION_WRAM + FACTION_SIZE * (f + 1)]
            out.append({"id": f + 1, "ruler": r[0], "playable": r[1], "b2": r[2], "daughters": r[3],
                        "relations": list(r[7:21]), "raw": bytes(r)})
        return out

    # ------------------------------------------------------------ faces
    def composite_record(self, code: int) -> tuple[int, list[int]]:
        """(type, [part number of slot 0..4]) of a composite face code."""
        first, _, recs, *_ = COMPOSITES[face_kind(code)]
        r = self.data[recs + 6 * (code - first):recs + 6 * (code - first) + 6]
        return r[5], list(r[:5])

    def composite_slots(self, kind: str) -> list[int]:
        """Number of part variants of each slot (the same for every type of the kind)."""
        _, _, _, _, offs, _, _ = COMPOSITES[kind]
        first = [le16(self.data, offs + 2 * k) for k in range(FACE_SLOTS)] + [25]
        return [first[k + 1] - first[k] for k in range(FACE_SLOTS)]

    def composite_part(self, kind: str, t: int, k: int, v: int) -> tuple[int, bytes]:
        """(byte offset in the 960-byte face, tile bytes) of variant v of slot k of type t."""
        _, _, _, parts, offs, pos, _ = COMPOSITES[kind]
        x, y = le16(self.data, pos + 20 * t + 4 * k), le16(self.data, pos + 20 * t + 4 * k + 2)
        p = self.p24(parts + 75 * t + 3 * (le16(self.data, offs + 2 * k) + v))
        return (y * FACE_W + x) * 32, self.lz(p)

    def face_bytes(self, code: int) -> bytes:
        """960 bytes of 4bpp tiles (5 x 6, row-major) the game puts in VRAM for a face code."""
        kind = face_kind(code)
        if kind == "portrait":
            return self.entry(PORTRAIT_ENTRY + code)
        t, parts = self.composite_record(code)
        buf = bytearray(FACE_BYTES)
        for k, v in enumerate(parts):
            o, d = self.composite_part(kind, t, k, v)
            buf[o:o + len(d)] = d
        return bytes(buf[:FACE_BYTES])

    def face_pixels(self, code: int) -> list[int]:
        """40x48 colour numbers of a face, row-major."""
        raw = self.face_bytes(code)
        out = [0] * (FACE_W * 8 * FACE_H * 8)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(raw[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_palette(self) -> list[int]:
        return self.palette(FACE_PALETTE)

    # ------------------------------------------------------------ strategic map
    def map_tilemap(self) -> list[int]:
        return [le16(self.data, MAP_TILEMAP + 2 * i) for i in range(MAP_W * MAP_H)]

    def map_palettes(self, frame: int = MAP_PALETTE_STILL) -> dict[int, list[tuple]]:
        return {2: self.palette_rgb(MAP_PALETTE_FRAMES + 32 * frame)}

    def map_rgb(self, frame: int = MAP_PALETTE_STILL) -> tuple[int, int, list]:
        """(width, height, RGB list) of the strategic map (BG1, before the owner colours)."""
        rgb = tiles_rgb(self.map_tilemap(), MAP_W, MAP_H, self.lz(MAP_TILES), 1, self.map_palettes(frame))
        return MAP_W * 8, MAP_H * 8, rgb

    def map_mask(self) -> list[int]:
        """Colour numbers (240 x 176) of the BG2 overlay tiles of the map (the owner-colour layer)."""
        d = self.lz(MAP_MASK)
        w = MAP_W * 8
        out = [0] * (w * (len(d) // 32 // MAP_W) * 8)
        for t in range(len(d) // 32):
            for i, v in enumerate(decode_tile(d[32 * t:32 * t + 32])):
                out[(t // MAP_W * 8 + i // 8) * w + t % MAP_W * 8 + i % 8] = v
        return out

    def map_regions(self) -> list[int]:
        """Country number (0 = none) of every pixel of the mask: the 4-connected region of each seed."""
        mk = self.map_mask()
        w = MAP_W * 8
        out = [0] * len(mk)
        for c, (x, y) in enumerate(MAP_REGION_SEEDS, 1):
            todo = [y * w + x]
            out[todo[0]] = c
            while todo:
                p = todo.pop()
                for q in (p - 1, p + 1, p - w, p + w):
                    if 0 <= q < len(mk) and abs(q % w - p % w) <= 1 and mk[q] == 1 and not out[q]:
                        out[q] = c
                        todo.append(q)
        return out

    def map_owner_pixels(self, owners: list[int]) -> list[int]:
        """Colour numbers of the owner layer (BG2) the game draws for owners[c - 1] of country c."""
        return [owners[c - 1] + 1 if c else 0 for c in self.map_regions()]

    def map_owner_rgb(self, owners: list[int]) -> tuple[int, int, list]:
        """(width, height, RGB list, None = transparent) of the owner layer."""
        pal = self.palette_rgb(MAP_OWNER_PALETTE)
        px = self.map_owner_pixels(owners)
        return MAP_W * 8, len(px) // (MAP_W * 8), [pal[v] if v else None for v in px]

    # ------------------------------------------------------------ battle fields
    def castle_cells(self, c: int) -> list[tuple[int, int]]:
        """(column, row) of the castle places of country c, in order (the first `castle` of them are used)."""
        rec = self.data[CASTLES + CASTLE_SLOTS * (c - 1):CASTLES + CASTLE_SLOTS * c]
        return [((b >> 4) - 1, (b & 15) - 1) for b in rec if b != 0xFF]

    def battle_grid(self, c: int, castles: int = 0) -> list[list[int]]:
        """14 x 12 cell bytes of country c's field (rows of columns; odd columns half a cell lower), with the
        first `castles` castle places turned into terrain 4 (城) as the game does when the battle starts."""
        d = self.entry(BATTLE_GRID + c - 1)
        g = [list(d[BATTLE_COLS * r:BATTLE_COLS * (r + 1)]) for r in range(BATTLE_ROWS)]
        for x, y in self.castle_cells(c)[:castles]:
            g[y][x] |= CASTLE_TERRAIN << 3
        return g

    def battle_tilemap(self, c: int, castles: int = 0) -> list[int]:
        """28 x 25 BG2 words of country c's field, with the first `castles` castles drawn."""
        d = self.entry(BATTLE_TILEMAP + c - 1)
        t = [le16(d, 2 * i) for i in range(BATTLE_TW * BATTLE_TH)]
        for x, y in self.castle_cells(c)[:castles]:
            ty = 2 * y + (x & 1)
            for k, e in enumerate(CASTLE_TILES):
                t[BATTLE_TW * (ty + k // 2) + 2 * x + k % 2] = e
        return t

    def battle_rgb(self, c: int, castles: int = 0) -> tuple[int, int, list]:
        pals = {p: self.palette_rgb(o) for p, o in BATTLE_PALETTES.items()}
        rgb = tiles_rgb(self.battle_tilemap(c, castles), BATTLE_TW, BATTLE_TH, self.entry(BATTLE_CHR),
                        BATTLE_CHR_FIRST, pals)
        return BATTLE_TW * 8, BATTLE_TH * 8, rgb
