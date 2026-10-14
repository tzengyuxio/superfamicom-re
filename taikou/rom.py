"""SFC 太閤立志伝 (KOEI, 1993) ROM decoding.

Offsets are file offsets of the headerless 1.5 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
The LZ decompressor is the shared one in tools/koei_lz.py. The program is compiled C: routines take their
arguments on the stack and call services through JSL $C0:8000.
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Taikou Risshiden (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

ENTRIES, ENTRY_COUNT = 0x1F2C1, 448     # 3-byte pointers to LZ streams ("entries" below)

# Font: glyph g = 16x16 1bpp, 32 bytes at FONT + 32 g (8x8 tiles TL TR BL BR, one byte per row).
# Text code 0x8140 + g, big-endian; 0x9140 + k stands for 0x8200 + 0x100 k (low byte 00 cannot be stored).
FONT, GLYPH_COUNT = 0x170000, 2048
TWO_BYTE_LAST = 0x8888                   # higher codes draw a blank (except the escapes)
KANA2 = 0x748                            # second kana set, used by the one-byte kana of the dialogue text

# Name table: 716 x 16 bytes: surname (7 bytes, NUL padded), given name (7), face code (LE16).
NAMES, NAME_COUNT, NAME_SIZE = 0x1C31D, 716, 16

# Start-of-game block: ROM INIT is copied to $7E:2000 (INIT_SIZE bytes) when a new game starts. Tables inside
# are given by WRAM address (ROM offset = INIT + address - 0x2000).
INIT, INIT_SIZE, WRAM_BASE = 0x183F0, 0x3F2D, 0x2000
FACTIONS, FACTION_COUNT, FACTION_SIZE = 0x2213, 20, 33
PERSONS, PERSON_COUNT, PERSON_SIZE = 0x24A7, 241, 54
CASTLE_COUNT = 125
CASTLE_STATES, CASTLE_STATE_COUNT, CASTLE_STATE_SIZE = 0x577D, 123, 16  # 安土 123 / 大坂 124 have none yet
# Persons 241-712 are not in the start block: same 54-byte records in ROM (they enter the game later).
LATER_PERSONS, LATER_COUNT = 0xB63E0, 472
PERSON_TOTAL = PERSON_COUNT + LATER_COUNT  # 713 records; name ids 713-715 have no record
STATS = ["外交", "内政", "魅力", "統率", "武力", "野心"]  # record +34..+39
SKILL_GRADES = "DCBA"                    # skill level 0-3 as the info screen shows it

# Castles: 125 x 17 bytes: name (9 bytes), 4 neighbour castles (FF = none), location LE16, cell, +16 unsolved.
CASTLES, CASTLE_SIZE = 0x15ECC, 17

# 3-byte pointer tables to NUL-terminated strings
STRING_TABLES = {"ranks": (0x5A639, 9), "skills": (0x16807, 8), "stat_names": (0x167D7, 6),
                 "formations": (0x16739, 7), "positions": (0x16771, 5), "weather": (0x16799, 4),
                 "units": (0x167B9, 3)}

# Faces: 32x40 = 4x5 4bpp tiles row-major (640 bytes), built by $CD:383F(code). Code bit 15 clear: portrait
# = LZ entry FACE_ENTRY + code; set: composed face (type (code >> 8) & 15, parts in the low 8 bits).
FACE_W, FACE_H, FACE_BYTES = 4, 5, 640
FACE_ENTRY, PORTRAIT_COUNT = 81, 258
FACE_PALETTE = 0xD8FC9                   # OBJ palette 1 (CGRAM 0x120)
COMP_TABLE = 0xD847E                     # 12 types x 12 bytes: 4 LE16 masks, 4 bytes (count | mask << 4)
COMP_PARTS = 0x162000                    # type t part pool at COMP_PARTS + COMP_POOL t, uncompressed tiles
COMP_POOL = 2560
COMP_TYPES, COMP_SLOTS, COMP_VARIANTS = 12, 4, 4

# Big map: 41 x 30 table of LE16 block numbers (0 = none); rows 0-22 are Japan, block n = 64 cell bytes at
# 64 (n - 1) of the LZ stream MAP_BLOCKS (decompressed to $7F:0000 at boot). Rows 24-29 hold 17 areas of 4 x 3
# blocks (numbers 0x20A-0x2D5) whose cells are at ROM AREA_CELLS + 64 (n - 0x20A) (not rendered here).
MAP_BLOCKS = 0x000000
BLOCK_TABLE, TABLE_W, TABLE_H = 0x5A911, 41, 30
MAP_ROWS = 23
BLOCK = 8                                # cells per block side; a cell is one 16x16 BG tile
AREA_CELLS, AREA_FIRST = 0x4000, 0x20A
SEA = 0x13                               # cell byte of blocks the table leaves empty
# Cell byte -> BG tilemap words ($C3:02B4). bit 7 clear: BG1 = T1[b], BG2 = T2[b] (Japan map tables).
# bit 7 set (object): E = OBJ_BG1 + 8 ((b >> 4) & 7); bit 3 ? (cell above, cell) = (E[1], E[3]) : (E[0], E[2]) on
# BG1; BG2 = OBJ_BG2 + 16 (bit 6) + 2 (b & 7).
T1, T2, OBJ_BG1, OBJ_BG2 = 0xAEBFF, 0xAEC85, 0xAED0B, 0xAED4B
# BG character data as VRAM holds it on the map (character base 0x8000): (VRAM byte address, entry, start, end)
MAP_CHR = [(0x8240, 71, 0x40, 0x200), (0x8400, 5, 0, 0x2C00), (0xB000, 20, 0x2C00, 0x5000)]
MAP_CHR_BASE = 0x8000
MAP_PALETTES = {2: 0xD8769, 3: 0xD8789, 4: 0xD87A9, 5: 0xDAF25, 6: 0xD97E1, 7: 0x15E28}

# Battle fields: field f ($7E:7F82) = LZ entry BATTLE_FIRST + f, 31 x 14 LE16 BG words (16x16 tiles, written to
# the BG tilemap at VRAM 0xF000) + 1 byte (unsolved). $C6:F885 loads it through the pointer table $C1:F6BA
# (= ENTRIES + 3 x 339): its entry 0 (LZ entry 339) is the fields' BG characters at VRAM 0x8400.
BATTLE_FIRST, BATTLE_COUNT, BATTLE_W, BATTLE_H = 347, 19, 31, 14
BATTLE_CHR_ENTRY, BATTLE_CHR_VRAM = 339, 0x8400
# palette 2 changes with the time of day (0xD91A9 is the daytime one seen at 桶狭間)
BATTLE_PALETTES = {2: 0xD91A9, 7: 0xD9289}


# One-byte kana of the dialogue text: 0xA1-0xDF in JIS X 0201 order, drawn as hiragana
KANA1 = "。「」、・をぁぃぅぇぉゃゅょっーあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわん゛゜"
KANA_MARKS = ({chr(ord(c)): chr(ord(c) + 1) for c in "かきくけこさしすせそたちつてとはひふへほ"} | {"う": "ゔ"},
              {chr(ord(c)): chr(ord(c) + 2) for c in "はひふへほ"})


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


def encode_glyph(g: int) -> bytes:
    """Text code of font glyph g (with the 0x9140 + k escape for low byte 00)."""
    code = 0x8140 + g
    if code & 0xFF == 0:
        code = 0x9140 + ((code - 0x8200) >> 8)
    return code.to_bytes(2, "big")


def is_composite(code: int) -> bool:
    return bool(code & 0x8000)


def composite_parts(code: int) -> tuple[int, list[int]]:
    """(type, [variant of part 0..3]) of a composed face code."""
    return code >> 8 & 15, [code >> 6 & 3, code >> 4 & 3, code >> 2 & 3, code & 3]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.lz_tables = koei_lz.find_tables(self.data)
        self.charset = load_charset()
        self._cache: dict[int, bytes] = {}

    # --- generic ---
    def lz(self, offset: int) -> bytes:
        return koei_lz.decompress(self.data, offset, self.lz_tables)[0]

    def entry(self, i: int) -> bytes:
        """Decompressed LZ entry i of the pointer table at ENTRIES."""
        if i not in self._cache:
            t = ENTRIES + 3 * i
            self._cache[i] = self.lz(int.from_bytes(self.data[t:t + 3], "little") & 0x3FFFFF)
        return self._cache[i]

    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g."""
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    def text(self, raw: bytes) -> str:
        """Game string -> str (stops at NUL). 0xA1-0xDF are the one-byte kana of the dialogue text (JIS X 0201
        order, shown as hiragana; DE / DF add (han)dakuten to the kana before), 0x0A a line break, 0x20-0x7E ASCII
        (spaces and printf formats); other single bytes become [xx]."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            c = raw[i]
            if 0xA1 <= c <= 0xDF:
                k = KANA1[c - 0xA1]
                if c in (0xDE, 0xDF) and out and out[-1] in KANA_MARKS[c - 0xDE]:
                    k = KANA_MARKS[c - 0xDE][out.pop()]
                out.append(k)
                i += 1
            elif c == 0x0A:
                out.append("\n")
                i += 1
            elif 0x81 <= c <= 0x91 and i + 1 < len(raw):
                code = c << 8 | raw[i + 1]
                if 0x9140 <= code < 0x9150:
                    code = 0x8200 + ((code - 0x9140) << 8)
                g = code - 0x8140
                out.append(self.charset[g] if 0 <= g < GLYPH_COUNT else f"[{code:04x}]")
                i += 2
            else:
                out.append(chr(c) if 0x20 <= c < 0x7F else f"[{c:02x}]")
                i += 1
        return "".join(out)

    def code_glyph(self, code: bytes) -> int:
        """Glyph the game draws for a two-byte text code: 0x8140 + g -> g up to 0x8888 (glyph 0x748), escapes
        0x9140 + k -> 0x8200 + 0x100 k; codes 0x8889-0x893F draw glyph 0 (blank)."""
        c = code[0] << 8 | code[1]
        if 0x9140 <= c < 0x9150:
            c = 0x8200 + ((c - 0x9140) << 8)
        return c - 0x8140 if c <= TWO_BYTE_LAST or c & 0xFF == 0 else 0

    def kana1_glyph(self, c: int, mark: int = 0) -> int:
        """Glyph of a one-byte kana 0xA6-0xDD: its hiragana in the second kana set (0x748-0x797); a following
        DE adds 1, DF adds 2."""
        return self.charset.index(KANA1[c - 0xA1], KANA2) + {0: 0, 0xDE: 1, 0xDF: 2}[mark]

    def glyph_codes(self, raw: bytes) -> list[int]:
        """Font glyph numbers of the two-byte codes of a string (up to NUL; one-byte codes skipped)."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            if 0x81 <= raw[i] <= 0x91 and i + 1 < len(raw):
                code = raw[i] << 8 | raw[i + 1]
                if 0x9140 <= code < 0x9150:
                    code = 0x8200 + ((code - 0x9140) << 8)
                out.append(code - 0x8140)
                i += 2
            else:
                i += 1
        return out

    def cstring(self, p: int) -> str:
        return self.text(self.data[p:self.data.index(b"\0", p) + 1])

    def string_table(self, name: str) -> list[str]:
        base, n = STRING_TABLES[name]
        return [self.cstring(int.from_bytes(self.data[base + 3 * i:base + 3 * i + 3], "little") & 0x3FFFFF)
                for i in range(n)]

    # --- names ---
    def names(self) -> list[dict]:
        """716 name entries: id, surname, given name, face code."""
        out = []
        for i in range(NAME_COUNT):
            r = self.data[NAMES + NAME_SIZE * i:NAMES + NAME_SIZE * (i + 1)]
            out.append({"id": i, "surname": self.text(r[0:7]), "given": self.text(r[7:14]), "face": le16(r, 14)})
        return out

    # --- start block ---
    def init_block(self) -> bytes:
        """The INIT_SIZE bytes the game copies to $7E:2000 when a new game starts."""
        return self.data[INIT:INIT + INIT_SIZE]

    def wram_table(self, addr: int, count: int, size: int) -> list[bytes]:
        o = INIT + addr - WRAM_BASE
        return [self.data[o + size * k:o + size * (k + 1)] for k in range(count)]

    def person_record(self, k: int) -> bytes:
        """54-byte record k (0-240 from the start block, 241-712 from LATER_PERSONS)."""
        if k < PERSON_COUNT:
            o = INIT + PERSONS - WRAM_BASE + PERSON_SIZE * k
        else:
            o = LATER_PERSONS + PERSON_SIZE * (k - PERSON_COUNT)
        return self.data[o:o + PERSON_SIZE]

    def persons(self) -> list[dict]:
        """713 person records. See docs/ROM_FORMAT.md §4."""
        names = self.names()
        out = []
        for k in range(PERSON_TOTAL):
            r = self.person_record(k)
            pid = le16(r, 0)
            n = names[pid]
            p = {"record": k, "id": pid, "raw": r, "surname": n["surname"], "given": n["given"], "face": n["face"],
                 "start": k < PERSON_COUNT, "positions": [(le16(r, 2 + 3 * i), r[4 + 3 * i]) for i in range(3)],
                 "faction": r[23], "castle": r[24], "rank": r[25], "w26": le16(r, 26), "b28": r[28], "b29": r[29],
                 "政略Lv": r[30], "b31": r[31], "b32": r[32], "戦術Lv": r[33],
                 "skills": [r[40] >> (6 - 2 * i) & 3 for i in range(4)] + [r[41] >> (6 - 2 * i) & 3 for i in range(3)],
                 "tail": r[42:54]}
            for i, s in enumerate(STATS):
                p[s] = r[34 + i]
            p["skills"].append(sum(p["skills"]) // 7)   # 文化 = mean of the other seven ($CD:005D)
            out.append(p)
        return out

    def factions(self) -> list[dict]:
        """20 factions of 33 bytes at $7E:2213: +0 daimyo record (FF = none), +1..+20 one byte per faction
        (unsolved, 0 for itself), +21 home castle, +22 LE16, +24..+32 unsolved."""
        out = []
        for k, r in enumerate(self.wram_table(FACTIONS, FACTION_COUNT, FACTION_SIZE)):
            out.append({"id": k, "raw": r, "daimyo": r[0], "relations": list(r[1:21]), "castle": r[21],
                        "w22": le16(r, 22), "tail": r[24:33]})
        return out

    def castles(self) -> list[dict]:
        """125 castles (static table) joined with their start-of-game state ($7E:577D, 16 bytes each; castles 123
        安土 and 124 大坂 have no state record at the start)."""
        states = self.wram_table(CASTLE_STATES, CASTLE_STATE_COUNT, CASTLE_STATE_SIZE)
        out = []
        for k in range(CASTLE_COUNT):
            r = self.data[CASTLES + CASTLE_SIZE * k:CASTLES + CASTLE_SIZE * (k + 1)]
            loc = le16(r, 13)
            c = {"id": k, "raw": r, "name": self.text(r[0:9]), "neighbours": [b for b in r[9:13] if b != 0xFF],
                 "location": loc, "block": (loc % TABLE_W, loc // TABLE_W), "cell": r[15], "b16": r[16], "state": None}
            if k < CASTLE_STATE_COUNT:
                s = states[k]
                c.update({"state": s, "lord": s[1], "faction": s[2], "s3": s[3], "s4": s[4], "s5": le16(s, 5),
                          "s7": le16(s, 7), "s9": s[9], "s10": s[10], "s11": le16(s, 11), "s13": s[13],
                          "s14": s[14], "s15": s[15]})
            out.append(c)
        return out

    # --- faces ---
    def composite_layout(self, t: int) -> list[tuple[int, int]]:
        """(20-bit cell mask, tiles per variant) of the 4 parts of type t; mask bit 19 = cell 0."""
        rec = self.data[COMP_TABLE + 12 * t:COMP_TABLE + 12 * t + 12]
        return [(le16(rec, 2 * k) << 4 | rec[8 + k] >> 4, rec[8 + k] & 15) for k in range(COMP_SLOTS)]

    def composite_part(self, t: int, k: int, v: int) -> dict[int, bytes]:
        """{cell: 32 tile bytes} that variant v of part k of type t writes ($CD:35CC)."""
        layout = self.composite_layout(t)
        src = COMP_PARTS + COMP_POOL * t + 32 * COMP_VARIANTS * sum(c for _, c in layout[:k])
        mask, cnt = layout[k]
        src += 32 * cnt * v
        out, n = {}, 0
        for cell in range(FACE_W * FACE_H):
            if mask >> (19 - cell) & 1 and n < cnt:
                out[cell] = self.data[src + 32 * n:src + 32 * n + 32]
                n += 1
        return out

    def face_tiles(self, code: int) -> bytes:
        """640 bytes of tiles the game builds for a face code."""
        if not is_composite(code):
            return self.entry(FACE_ENTRY + code)[:FACE_BYTES]
        t, parts = composite_parts(code)
        out = bytearray(FACE_BYTES)
        for k, v in enumerate(parts):
            for cell, raw in self.composite_part(t, k, v).items():
                out[32 * cell:32 * cell + 32] = raw
        return bytes(out)

    def face_palette(self) -> list[int]:
        return [le16(self.data, FACE_PALETTE + 2 * i) for i in range(16)]

    def face_pixels(self, code: int = 0, tiles: bytes | None = None) -> list[int]:
        """32x40 colour numbers, row-major."""
        tiles = self.face_tiles(code) if tiles is None else tiles
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, code: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(code)]

    # --- big map ---
    def block_table(self) -> list[list[int]]:
        return [[le16(self.data, BLOCK_TABLE + 2 * (TABLE_W * y + x)) for x in range(TABLE_W)] for y in range(TABLE_H)]

    def map_blocks(self) -> bytes:
        """Cell bytes of the Japan map blocks (64 per block), as decompressed to $7F:0000."""
        if -1 not in self._cache:
            self._cache[-1] = self.lz(MAP_BLOCKS)
        return self._cache[-1]

    def map_blocks_at_start(self) -> bytes:
        """map_blocks() as a new game leaves them ($C3:0DB2): for castles 0-122 the two cells at the castle's
        location get bits 4-5 = castle state +14 bits 0-1 (which castle icon is drawn)."""
        out = bytearray(self.map_blocks())
        table = self.block_table()
        for c in self.castles()[:CASTLE_STATE_COUNT]:
            bx, by = c["block"]
            o = 64 * (table[by][bx] - 1) + c["cell"]
            for i in (o, o + 1):
                out[i] = out[i] & 0xCF | (c["s14"] & 3) << 4
        return bytes(out)

    def map_cells(self, blocks: bytes | None = None, table: list[list[int]] | None = None) -> list[list[int]]:
        """(TABLE_W * 8) x (MAP_ROWS * 8) cell bytes of the Japan map; where the table has no block the game
        fills the cells with SEA ($C3:0260)."""
        blocks = self.map_blocks() if blocks is None else blocks
        table = self.block_table() if table is None else table
        w = TABLE_W * BLOCK
        out = [[SEA] * w for _ in range(MAP_ROWS * BLOCK)]
        for by in range(MAP_ROWS):
            for bx in range(TABLE_W):
                n = table[by][bx]
                if not n:
                    continue
                cells = blocks[64 * (n - 1):64 * n]
                for i, c in enumerate(cells):
                    out[by * BLOCK + i // 8][bx * BLOCK + i % 8] = c
        return out

    def cell_words(self, b: int) -> tuple[int, int, int | None]:
        """(BG1 word, BG2 word, BG1 word for the cell above or None) of a Japan map cell byte."""
        d = self.data
        if not b & 0x80:
            return le16(d, T1 + 2 * b), le16(d, T2 + 2 * b), None
        e = OBJ_BG1 + 8 * (b >> 4 & 7)
        above, here = (le16(d, e + 2), le16(d, e + 6)) if b & 8 else (le16(d, e), le16(d, e + 4))
        return here, le16(d, OBJ_BG2 + (0x10 if b & 0x40 else 0) + 2 * (b & 7)), above

    def map_tilemaps(self, cells: list[list[int]]) -> tuple[list[list[int]], list[list[int]]]:
        """(BG1, BG2) 16x16-tile tilemaps of a grid of cells, in the order the game writes them: an object cell
        also overwrites BG1 of the cell above. BG2 0 stays 0 (the Japan map's default)."""
        h, w = len(cells), len(cells[0])
        bg1 = [[0] * w for _ in range(h)]
        bg2 = [[0] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                here, under, above = self.cell_words(cells[y][x])
                bg1[y][x], bg2[y][x] = here, under
                if above is not None and y > 0:
                    bg1[y - 1][x] = above
        return bg1, bg2

    def map_chr(self) -> bytes:
        """64 KB VRAM image with the map's BG characters in place (rest 0)."""
        v = bytearray(0x10000)
        for addr, e, lo, hi in MAP_CHR:
            v[addr:addr + hi - lo] = self.entry(e)[lo:hi]
        return bytes(v)

    def map_palettes(self) -> dict[int, list[int]]:
        return {p: [le16(self.data, o + 2 * i) for i in range(16)] for p, o in MAP_PALETTES.items()}

    def map_rgb(self) -> tuple[int, int, list]:
        """(width, height, RGB list) of the whole Japan map: BG2, then BG1 on top (colour 0 transparent)."""
        cells = self.map_cells(self.map_blocks_at_start())
        bg1, bg2 = self.map_tilemaps(cells)
        h, w = len(cells), len(cells[0])
        vram = self.map_chr()
        pals = {p: [bgr555_rgb(c) for c in v] for p, v in self.map_palettes().items()}
        out: list = [(0, 0, 0)] * (w * 16 * h * 16)
        for layer, opaque in ((bg2, True), (bg1, False)):
            draw_16(out, layer, w, vram, pals, opaque)
        return w * 16, h * 16, out

    # --- battle fields ---
    def battle_tilemap(self, f: int) -> list[list[int]]:
        d = self.entry(BATTLE_FIRST + f)
        return [[le16(d, 2 * (BATTLE_W * y + x)) for x in range(BATTLE_W)] for y in range(BATTLE_H)]

    def battle_tail(self, f: int) -> int:
        return self.entry(BATTLE_FIRST + f)[2 * BATTLE_W * BATTLE_H]

    def battle_chr(self) -> bytes:
        """64 KB VRAM image with the battle fields' BG characters in place (rest 0)."""
        v = bytearray(0x10000)
        d = self.entry(BATTLE_CHR_ENTRY)
        v[BATTLE_CHR_VRAM:BATTLE_CHR_VRAM + len(d)] = d
        return bytes(v)

    def battle_palettes(self) -> dict[int, list[int]]:
        return {p: [le16(self.data, o + 2 * i) for i in range(16)] for p, o in BATTLE_PALETTES.items()}

    def battle_rgb(self, f: int) -> tuple[int, int, list]:
        """(width, height, RGB list) of battle field f."""
        pals = {p: [bgr555_rgb(c) for c in v] for p, v in self.battle_palettes().items()}
        out: list = [(0, 0, 0)] * (BATTLE_W * 16 * BATTLE_H * 16)
        draw_16(out, self.battle_tilemap(f), BATTLE_W, self.battle_chr(), pals, True)
        return BATTLE_W * 16, BATTLE_H * 16, out


def draw_16(out: list, tilemap: list[list[int]], w: int, vram: bytes, pals: dict, opaque: bool) -> None:
    """Draw a 16x16-tile BG tilemap (tile n = 8x8 tiles n, n+1, n+16, n+17 from MAP_CHR_BASE) into an RGB list
    of width w*16. Entry 0 is skipped unless opaque; colour 0 is drawn only when opaque."""
    width = w * 16
    decoded: dict[int, list[int]] = {}
    for ty, row in enumerate(tilemap):
        for tx, e in enumerate(row):
            if not e and not opaque:
                continue
            pal = pals.get(e >> 10 & 7)
            if pal is None:
                continue
            n = e & 0x3FF
            for q, sub in enumerate((n, n + 1, n + 16, n + 17)):
                a = MAP_CHR_BASE + 32 * sub
                if a not in decoded:
                    decoded[a] = decode_tile(vram[a:a + 32])
                px = decoded[a]
                qx, qy = (q & 1) * 8, (q >> 1) * 8
                if e & 0x4000:
                    qx = 8 - qx
                if e & 0x8000:
                    qy = 8 - qy
                for k, v in enumerate(px):
                    if not v and not opaque:
                        continue
                    y, x = divmod(k, 8)
                    if e & 0x4000:
                        x = 7 - x
                    if e & 0x8000:
                        y = 7 - y
                    out[(ty * 16 + qy + y) * width + tx * 16 + qx + x] = pal[v]
