"""SFC リーディングカンパニー (KOEI) ROM decoding.

Headerless 1 MB LoROM image. The program is native 65816 code compiled from C (same engine as エアーマネージメント
II: service dispatcher $00:8000, printf services 3C / 43 / 4F / 61, sprintf 55). Graphics live in 254 named files
(file table at 0x6000), many of them KOEI LZ streams (tools/koei_lz.py). The scenario tables are in bank $02, the
name tables in bank $0C. See leading/docs/ROM_FORMAT.md.
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz
from paths import ORIGINAL

DEFAULT_ROM = os.path.join(ORIGINAL, "Leading Company (Japan).zip")

FILE_TABLE = 0x6000             # 16-byte entries: name[8], bank LE16, addr LE16, size LE32; name[0] = 0 ends


def lorom(bank: int, addr: int) -> int:
    return (bank & 0x7F) * 0x8000 + (addr & 0x7FFF)


# ---------------------------------------------------------------- name tables (bank $0C)
FORMAT_COUNT = 4                # consortia (協議会) = VTR formats
FORMAT_NAME = (0x0C, 0xDF91)    # 4 pointers: jvd be nvx vcd (the font draws a-z as A-Z)
MAKER_COUNT = 12
MAKER_NAME = (0x0C, 0xDFAC)     # 12 pointers: default maker names; maker i belongs to format i % 4 in the menu
FACILITY_LEVEL = (0x0C, 0xE022)  # 5 x LE16: 50 100 200 400 800 (unsolved)
GRADE_COUNT = 8
GRADE_PRICE = (0x0C, 0xE02C)    # 8 x LE16: list price in thousand yen by grade (basic1 = 400 = ¥400,000)
GRADE_NAME = (0x0C, 0xE03C)     # 8 pointers: basic1 basic2 standard1-3 super1-2 pro
GRADE_PRICE_TEXT = (0x0C, 0xE092)  # 8 pointers: the same prices as text
FEATURE_COUNT = 9
FEATURE = (0x0C, 0xE0C8)        # 9 x 25 bytes: bit LE16, name SJIS[16], 7 bytes (unsolved)
PROMOTION_COUNT = 12
PROMOTION_NAME = (0x0C, 0xE4CA)  # 12 pointers: sales promotions (販促物配布 ... ＴＶ番組提供)
DIFFICULTY = ["beginner grade", "medium grade", "high grade"]      # $02:DA5D, chosen after the format

# ---------------------------------------------------------------- scenarios (bank $02), built by $02:BF2B
SCENARIO_COUNT = 2
SCENARIO_YEARS = ["1970-1990", "1980-2000"]      # $02:DA46 / $02:DA54; the scenario index is WRAM $46DE
SCEN_FEATURE = (0x02, 0xDDC3, 0x2D)     # 9 x 5 bytes per scenario -> WRAM feature record + 0x18
SCEN_PRODUCT = (0x02, 0xDE1D, 0x5E8)    # 4 formats x 6 products x 63 bytes per scenario -> WRAM $4E19 as is
SCEN_FORMAT = (0x02, 0xDB83, 0x48)      # 4 x 18 bytes per scenario
SCEN_MAKER = (0x02, 0xDC13, 0xD8)       # 12 x 18 bytes per scenario
SCEN_5401 = (0x02, 0xE9ED, 0x140)       # -> WRAM $5401 as is (unsolved)
SCEN_5541 = (0x02, 0xEC6D, 0xA8)        # -> WRAM $5541, then 4 x 14-byte format records are recomputed
SCEN_6E05 = (0x02, 0xEDBD, 0x844)       # -> WRAM $6E05 as is (unsolved)
PRODUCT_SIZE, PRODUCTS_PER_FORMAT = 0x3F, 6

# WRAM of the game state ($7E:xxxx)
WRAM_SCENARIO = 0x46DE
WRAM_MAKER, MAKER_SIZE = 0x4785, 0x67           # 12 records; name at +2
WRAM_FORMAT, FORMAT_SIZE = 0x4C59, 0x70         # 4 records; name at +4
WRAM_PRODUCT = 0x4E19                           # format f, slot p at + f * 0x17A + p * 0x3F
WRAM_FEATURE, FEATURE_SIZE = 0x5627, 0x1D       # 9 records
WRAM_CELL, CELL_SIZE, CELL_COUNT = 0x5785, 0x5A, 64     # 8 x 8 market grid cells
WRAM_5401, WRAM_5541, WRAM_6E05 = 0x5401, 0x5541, 0x6E05

# ---------------------------------------------------------------- faces
# 7 kinds ($01:C491: pointers to the file names), 40 x 48 = 5 x 6 4bpp tiles row-major (960 bytes), followed by
# 3 strips of 5 x 3 tiles (480 bytes each) that the talking / blinking animation copies over tile rows 1-3.
# One record = 2400 bytes. All faces use the palette file KAO ($01:A58F loads it as sprite palette 7).
FACE_KINDS = ["PRESIDEN", "COMPTOP", "SECRETAR", "MANLABO", "MANFACTO", "MANBUSID", "MANACCOU"]
FACE_KIND_TABLE = (0x01, 0xC491)
FACE_GROUPS = ["会長", "社長", "秘書", "部長（開発）", "部長（生産）", "部長（営業）", "部長（経理）"]
FACE_W, FACE_H, FACE_BYTES, FACE_RECORD = 5, 6, 960, 2400
STRIP_BYTES = 480
FACE_PALETTE_FILE = "KAO"
FACE_ROUTINE = 0x01A58F         # face draw: stack +8 kind, +10 image; KAO -> CGRAM 0x1E0, face -> VRAM


# ---------------------------------------------------------------- town map (main screen)
# BG2: the office district OFFCBACK (palette 2, tilemap 32 x 18, tiles at VRAM byte 0x6000). BG1: 4 building lots
# of 6 x 6 tiles at tile columns 3 / 10 / 17 / 24, rows 2-7, palette 3 = file EQUIP; lot n uses BG1 tiles
# 0x3E + 36 n. A building is one 1152-byte variant of BUSI_L1-5 (営業所), FACT_L1-5 (工場), LABO_L1-5 (研究所).
TOWN_FILE, TOWN_ROWS = "OFFCBACK", 18
TOWN_PALETTE, TOWN_TILES_VRAM, TOWN_TILEMAP_VRAM = 2, 0x6000, 0xF000
BUILDING_KINDS = {"BUSI": "営業所", "FACT": "工場", "LABO": "研究所"}
BUILDING_BYTES, BUILDING_VARIANTS = 1152, 5
BUILDING_PALETTE_FILE, BUILDING_PALETTE = "EQUIP", 3
LOT_COLUMNS, LOT_ROW, LOT_TILE0, BG1_TILEMAP_VRAM = (3, 10, 17, 24), 2, 0x3E, 0xE800


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return tuple(((c >> s) & 31) * 255 // 31 for s in (0, 5, 10))


def tiles4(data: bytes, n: int) -> list[list[list[int]]]:
    """n 8x8 4bpp SNES tiles -> [tile][y][x]."""
    out = []
    for t in range(n):
        o = t * 32
        out.append([[((data[o + 2 * y] >> (7 - x)) & 1) | ((data[o + 2 * y + 1] >> (7 - x)) & 1) << 1
                     | ((data[o + 16 + 2 * y] >> (7 - x)) & 1) << 2 | ((data[o + 17 + 2 * y] >> (7 - x)) & 1) << 3
                     for x in range(8)] for y in range(8)])
    return out


def le16(b: bytes, o: int) -> int:
    return b[o] | b[o + 1] << 8


def s16(v: int) -> int:
    return v - 0x10000 if v & 0x8000 else v


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        if path.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
        else:
            with open(path, "rb") as f:
                data = f.read()
        self.data = data[len(data) % 0x8000:]
        self.lz_tables = koei_lz.find_tables(self.data)

    # ------------------------------------------------------------ basics
    def ptr(self, o: int) -> int:
        d = self.data
        return lorom(d[o + 2], d[o] | d[o + 1] << 8)

    def cstr(self, o: int) -> str:
        d = self.data
        return d[o:d.index(b"\0", o)].decode("cp932")

    def strings(self, where: tuple[int, int], n: int) -> list[str]:
        o = lorom(*where)
        return [self.cstr(self.ptr(o + 3 * i)) for i in range(n)]

    def words(self, where: tuple[int, int], n: int) -> list[int]:
        o = lorom(*where)
        return [le16(self.data, o + 2 * i) for i in range(n)]

    def files(self) -> list[dict]:
        out, o, d = [], FILE_TABLE, self.data
        while d[o]:
            bank, addr = d[o + 8] | d[o + 9] << 8, d[o + 10] | d[o + 11] << 8
            out.append({"index": len(out), "name": d[o:o + 8].split(b"\0")[0].decode("ascii"), "bank": bank,
                        "addr": addr, "offset": lorom(bank, addr), "size": int.from_bytes(d[o + 12:o + 16], "little")})
            o += 16
        return out

    def file(self, name: str) -> dict:
        """The first file of that name (the game's lookup $00:98DE scans from the start)."""
        return next(f for f in self.files() if f["name"] == name)

    def raw(self, name: str) -> bytes:
        f = self.file(name)
        return self.data[f["offset"]:f["offset"] + f["size"]]

    def lz(self, name: str) -> bytes:
        return koei_lz.decompress(self.data, self.file(name)["offset"], self.lz_tables)[0]

    def is_lz(self, f: dict) -> int | None:
        """Unpacked size if the file is one KOEI LZ stream filling the file, else None."""
        try:
            out, end = koei_lz.decompress(self.data, f["offset"], self.lz_tables)
        except (ValueError, IndexError):
            return None
        return len(out) if 0 <= f["offset"] + f["size"] - end <= 2 else None

    # ------------------------------------------------------------ names
    def formats(self) -> list[str]:
        return self.strings(FORMAT_NAME, FORMAT_COUNT)

    def maker_names(self) -> list[str]:
        return self.strings(MAKER_NAME, MAKER_COUNT)

    def grades(self) -> list[dict]:
        names, prices = self.strings(GRADE_NAME, GRADE_COUNT), self.words(GRADE_PRICE, GRADE_COUNT)
        text = self.strings(GRADE_PRICE_TEXT, GRADE_COUNT)
        return [{"index": i, "name": names[i], "price": prices[i], "price_text": text[i]} for i in range(GRADE_COUNT)]

    def features(self) -> list[dict]:
        o, d = lorom(*FEATURE), self.data
        out = []
        for i in range(FEATURE_COUNT):
            r = d[o + 25 * i:o + 25 * i + 25]
            out.append({"index": i, "bit": le16(r, 0), "name": r[2:18].split(b"\0")[0].decode("cp932"),
                        "b18": r[18], "w19": le16(r, 19), "w21": le16(r, 21), "w23": le16(r, 23), "raw": bytes(r)})
        return out

    def promotions(self) -> list[str]:
        return self.strings(PROMOTION_NAME, PROMOTION_COUNT)

    def facility_levels(self) -> list[int]:
        return self.words(FACILITY_LEVEL, 5)

    # ------------------------------------------------------------ scenarios
    def scen(self, table: tuple[int, int, int], scenario: int) -> bytes:
        bank, addr, size = table
        o = lorom(bank, addr) + scenario * size
        return self.data[o:o + size]

    def format_records(self, scenario: int) -> list[dict]:
        """18-byte records: id LE16 (FFFF = the format is not in this scenario), 4 x LE32 sales of the last four
        quarters before the start in million yen (the fourth is 0: the game simulates it before the first turn)."""
        r = self.scen(SCEN_FORMAT, scenario)
        names = self.formats()
        out = []
        for i in range(FORMAT_COUNT):
            b = r[18 * i:18 * i + 18]
            fid = le16(b, 0)
            out.append({"index": i, "name": names[i], "present": fid != 0xFFFF,
                        "sales": [int.from_bytes(b[2 + 4 * k:6 + 4 * k], "little") for k in range(4)],
                        "raw": bytes(b)})
        return out

    def maker_records(self, scenario: int) -> list[dict]:
        """18-byte records: format LE16 (FFFF = none), leader flag LE16, 4 x LE16 trust (信用度) toward formats
        0-3, product slot LE16 (FFFF = none; the product is format/slot of the products table), LE16 and LE16
        at +14 / +16 (unsolved, copied to WRAM +0x1D / +0x1F)."""
        r = self.scen(SCEN_MAKER, scenario)
        names = self.maker_names()
        out = []
        for i in range(MAKER_COUNT):
            b = r[18 * i:18 * i + 18]
            fmt, prod = le16(b, 0), le16(b, 12)
            out.append({"index": i, "name": names[i], "format": None if fmt == 0xFFFF else fmt,
                        "leader": le16(b, 2), "trust": [le16(b, 4 + 2 * k) for k in range(4)],
                        "product": None if prod == 0xFFFF else prod, "w14": le16(b, 14), "w16": le16(b, 16),
                        "raw": bytes(b)})
        return out

    def products(self, scenario: int) -> list[dict]:
        """63-byte product records, 6 slots per format (WRAM $4E19). Only fields checked against the game are
        named; see ROM_FORMAT.md §5 for the layout."""
        r = self.scen(SCEN_PRODUCT, scenario)
        out = []
        for f in range(FORMAT_COUNT):
            for p in range(PRODUCTS_PER_FORMAT):
                o = f * PRODUCTS_PER_FORMAT * PRODUCT_SIZE + p * PRODUCT_SIZE
                b = r[o:o + PRODUCT_SIZE]
                if le16(b, 2) == 0xFFFF:
                    continue
                out.append({"format": f, "slot": p, "state": le16(b, 2), "name": b[4:13].split(b"\0")[0].decode(),
                            "grade": b[0x0E], "cell_col": b[0x0F], "maker": b[0x10], "contract": b[0x11],
                            "rate": le16(b, 0x12), "freshness": le16(b, 0x21),
                            "operating_rate": le16(b, 0x25), "awareness": le16(b, 0x27), "raw": bytes(b)})
        return out

    def feature_state(self, scenario: int) -> list[bytes]:
        r = self.scen(SCEN_FEATURE, scenario)
        return [r[5 * i:5 * i + 5] for i in range(FEATURE_COUNT)]

    def scenario_wram(self, scenario: int) -> dict[int, bytes]:
        """{WRAM address: bytes} that $02:BF2B writes from ROM tables (direct copies and the record fields it
        copies one by one), for comparing with the game's WRAM right after the scenario is built. Maker records
        +0x18 hold a 24-bit pointer to the maker's product (or 0)."""
        out: dict[int, bytes] = {}
        feats = self.features()
        for i, st in enumerate(self.feature_state(scenario)):
            out[WRAM_FEATURE + FEATURE_SIZE * i] = feats[i]["raw"][:24] + st
        out[WRAM_PRODUCT] = self.scen(SCEN_PRODUCT, scenario)
        for f in self.format_records(scenario):
            a = WRAM_FORMAT + FORMAT_SIZE * f["index"]
            out[a] = f["raw"][:2]
            out[a + 0x40] = f["raw"][2:18]
        for m in self.maker_records(scenario):
            a, b = WRAM_MAKER + MAKER_SIZE * m["index"], m["raw"]
            out[a + 0x0C] = b[0:12]
            p = 0 if m["product"] is None else self.product_pointer(m["format"], m["product"])
            out[a + 0x18] = p.to_bytes(3, "little")
            out[a + 0x1D] = b[14:18]
        out[WRAM_5401] = self.scen(SCEN_5401, scenario)
        out[WRAM_6E05] = self.scen(SCEN_6E05, scenario)
        # $5541: 4 x 14-byte format records are recomputed for the formats present; the rest is the copy
        t = self.scen(SCEN_5541, scenario)
        for f in self.format_records(scenario):
            if not f["present"]:
                out[WRAM_5541 + 14 * f["index"]] = t[14 * f["index"]:14 * f["index"] + 14]
        out[WRAM_5541 + 56] = t[56:]
        out[WRAM_CELL] = self.cell_block(scenario)
        return out

    def product_pointer(self, fmt: int, slot: int) -> int:
        return 0x7E0000 + WRAM_PRODUCT + fmt * PRODUCTS_PER_FORMAT * PRODUCT_SIZE + slot * PRODUCT_SIZE

    def cell_block(self, scenario: int) -> bytes:
        """WRAM $5785 as $02:C4E4 builds it: per cell (0x5A bytes) the product count LE16 at +0, for each format f
        a 24-bit pointer at +2 + 21 f to its (last) product in the cell, and LE32 3000 at +0x56."""
        out = bytearray(CELL_SIZE * CELL_COUNT)
        for i, prods in enumerate(self.cells(scenario)):
            o = CELL_SIZE * i
            out[o:o + 2] = len(prods).to_bytes(2, "little")
            for f, p in prods:
                out[o + 2 + 21 * f:o + 5 + 21 * f] = self.product_pointer(f, p).to_bytes(3, "little")
            out[o + 0x56:o + 0x5A] = (3000).to_bytes(4, "little")
        return bytes(out)

    def cells(self, scenario: int) -> list[list[tuple[int, int]]]:
        """The 8 x 8 market grid ($02:C4E4): cell grade * 8 + col -> [(format, slot)] of the products placed there
        (the row is the product's grade +0x0E, the column +0x0F)."""
        out = [[] for _ in range(CELL_COUNT)]
        for p in self.products(scenario):
            out[p["grade"] * 8 + p["cell_col"]].append((p["format"], p["slot"]))
        return out

    # ------------------------------------------------------------ faces
    def face_file(self, kind: int) -> dict:
        names = self.strings(FACE_KIND_TABLE, len(FACE_KINDS))
        assert names[kind] == FACE_KINDS[kind]
        return self.file(names[kind])

    def face_count(self, kind: int) -> int:
        return self.face_file(kind)["size"] // FACE_RECORD

    def face_bytes(self, kind: int, image: int) -> bytes:
        """The 960 bytes the game copies to VRAM for the face (record image * 2400 of the kind's file)."""
        o = self.face_file(kind)["offset"] + image * FACE_RECORD
        return self.data[o:o + FACE_BYTES]

    def strip_bytes(self, kind: int, image: int, strip: int) -> bytes:
        o = self.face_file(kind)["offset"] + image * FACE_RECORD + FACE_BYTES + strip * STRIP_BYTES
        return self.data[o:o + STRIP_BYTES]

    def face_palette(self) -> list[int]:
        p = self.raw(FACE_PALETTE_FILE)
        return [le16(p, 2 * i) for i in range(16)]

    def face_pixels(self, kind: int, image: int, strip: int | None = None) -> list[list[int]]:
        """40 x 48 colour indices; with strip 0-2 the strip is laid over tile rows 1-3 like the animation does."""
        data = bytearray(self.face_bytes(kind, image))
        if strip is not None:
            data[160:160 + STRIP_BYTES] = self.strip_bytes(kind, image, strip)
        t = tiles4(bytes(data), FACE_W * FACE_H)
        return [[t[(y // 8) * FACE_W + x // 8][y % 8][x % 8] for x in range(FACE_W * 8)] for y in range(FACE_H * 8)]

    def face_rgb(self, kind: int, image: int, strip: int | None = None) -> list[list[tuple[int, int, int]]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [[pal[v] for v in row] for row in self.face_pixels(kind, image, strip)]

    def faces(self) -> list[dict]:
        """Every face in kind order: PRESIDEN 4 (会長), COMPTOP 12 (社長), SECRETAR 12, MAN* 4 each."""
        return [{"kind": k, "file": FACE_KINDS[k], "group": FACE_GROUPS[k], "image": i}
                for k in range(len(FACE_KINDS)) for i in range(self.face_count(k))]

    # ------------------------------------------------------------ town map (main screen)
    def town_background(self) -> dict:
        """OFFCBACK (LZ): BG2 palette (CGRAM 0x40, palette 2) 32 bytes, tilemap 32 x 18 words, 151 4bpp tiles
        (VRAM byte 0x6000)."""
        u = self.lz(TOWN_FILE)
        tm = u[32:32 + 64 * TOWN_ROWS]
        return {"palette": u[:32], "tilemap": tm, "tiles": u[32 + 64 * TOWN_ROWS:]}

    def building(self, kind: str, level: int, variant: int) -> bytes:
        """1152 bytes = 36 4bpp tiles (6 x 6, row-major) of BUSI / FACT / LABO _L1-5, variant 0-4."""
        return self.lz(f"{kind}_L{level}")[variant * BUILDING_BYTES:(variant + 1) * BUILDING_BYTES]

    def building_palette(self) -> bytes:
        return self.raw(BUILDING_PALETTE_FILE)[:32]


def render_tilemap(tilemap: bytes, tiles: bytes, palettes: dict[int, bytes], cols: int, rows: int,
                   tile_base: int = 0) -> list[list[tuple[int, int, int] | None]]:
    """RGB pixels (None = colour 0) of a 4bpp tilemap; palettes {palette number: 32 bytes}."""
    t = tiles4(tiles, len(tiles) // 32)
    out = [[None] * (cols * 8) for _ in range(rows * 8)]
    for ty in range(rows):
        for tx in range(cols):
            e = le16(tilemap, 2 * (ty * cols + tx))
            n, pal = (e & 0x3FF) - tile_base, (e >> 10) & 7
            if not 0 <= n < len(t):
                continue
            p = palettes[pal]
            for y in range(8):
                for x in range(8):
                    v = t[n][7 - y if e & 0x8000 else y][7 - x if e & 0x4000 else x]
                    if v:
                        out[ty * 8 + y][tx * 8 + x] = bgr555_rgb(le16(p, 2 * v))
    return out
