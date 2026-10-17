"""SFC トップマネジメントII (KOEI) ROM decoding.

Headerless 1.5 MB LoROM image. Like エアーマネージメントII the program is native 65816 code compiled from C
(banks $00-$1A, file 0x00000-0xD7FFF) and the resources live in 249 named files (file table at 0x6000), most of
them KOEI LZ streams (tools/koei_lz.py). Game tables are in bank $01 (3-byte pointers to Shift-JIS strings and
fixed-size records); some per-scenario values are immediates in the setup code (bank $06 / $07).
See topman2/docs/ROM_FORMAT.md.
"""
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Top Management II (Japan).zip")

FILE_TABLE = 0x6000             # 16-byte entries: name[8], addr LE16, bank LE16, size LE32; name[0] = 0 ends


def lorom(bank: int, addr: int) -> int:
    return (bank & 0x7F) * 0x8000 + (addr & 0x7FFF)


# ---------------------------------------------------------------- bank $01 tables (CPU address $01:xxxx)
PREF_COUNT = 47
PREF_NAME = 0xD3CF              # 47 pointers: prefecture name (北海道 .. 沖縄, JIS order)
PREF_POP = 0xC9CB               # 5 x 47 LE16: prefecture population (万人), one record per period
POP_PERIODS = 5                 # $07:A403 picks the record by the start year: < 1980, < 1985, < 1990, < 1995, else
POP_YEAR_LIMITS = [1980, 1985, 1990, 1995]
PREF_SMALL_XY = 0xCBAD          # 47 x (x, y) LE16: screen position on the JAPANL screen (map at (16, 24); + 8 lands
#                                 inside the prefecture; inferred from the image, its use not traced)
PREF_MAP_XY = 0xCC69            # 47 x (x, y) LE16: about (12, 19) + the centre of the prefecture's JAPANS runs (a
#                                 screen position, unsolved); 31 鳥取 / 32 島根 are swapped
PREF_SHAPE = 0xCD25             # 47 x [count, vertical, count x (x, y, len)]: runs that fill the prefecture on JAPANS
TABLE_CBA1 = 0xCBA1             # 6 x LE16 = 10000 7500 5000 5000 7500 10000 (unsolved)
HQ_PAIRS = 0xC661               # 15 x 2 LE16: (place A, place B), 1-based prefecture; PRESENT MODE start places
PRODUCT_SHORT = 0xD54F          # 3 pointers: DTOP LTOP NOTE
PRODUCT = 0xD567                # 3 pointers: DESKTOP LAPTOP NOTE
PRODUCT_JA = 0xD584             # 3 pointers: デスクトップ ラップトップ ノ－トブック
SCENARIO_NAME = 0xD5E9          # 9 pointers: 6 PRESENT MODE scenarios, then the 3 FREE MODE lengths
LEVEL = 0xD6C1                  # 5 pointers: BEGINNER .. PRO
INDUSTRY = 0xD6EE               # 4 pointers: the industries of the stock market (電子産業 ..)
NEWS = 0xD7EF                   # 26 pointers: newspaper headlines
PRODUCT_COUNT, SCENARIO_COUNT, FREE_COUNT, LEVEL_COUNT, INDUSTRY_COUNT, NEWS_COUNT = 3, 6, 3, 5, 4, 26

# ---------------------------------------------------------------- bank $06 setup code
COMPANY_COUNT = 3
COMPANY_NAME = [(0x06, 0xF2A2), (0x06, 0xF2AF), (0x06, 0xF2BC)]   # default names, copied by $06:8A1A
SCENARIO_YEARS_CODE = (0x06, 0xA4E3)    # 6 x {LDA #start; STA $2812; LDA #end; STA $2810} (switch on scenario)
SCENARIO_DESC_CODE = (0x06, 0x9973)     # 8 x {PEA bank; PEA lo} 31 bytes apart: page text of scenarios 1-6, free
FREE_LONG_YEARS = (1978, 1997)          # FREE MODE long scenario; short / middle: start chosen, end = start + 4 / 9

# WRAM of the game state ($7E:xxxx)
WRAM_SCENARIO = 0x280C          # LE16 scenario (0-5 PRESENT, 6-8 FREE)
WRAM_END_YEAR = 0x2810          # LE16
WRAM_START_YEAR = 0x2812        # LE16
WRAM_COMPANY = 0x2820           # 3 x 21 bytes: MAN flag LE16, home prefecture (1-based) LE16, (same, set at start),
#                                 name (Shift-JIS, 15 bytes)
COMPANY_SIZE = 21
WRAM_PLACES = 0x3638            # 3 x 48-bit mask: bit p = the company has an office in prefecture p (0-based)
WRAM_POP = 0x4417               # 47 x LE16: the population record of the start year

# ---------------------------------------------------------------- faces
# A face is 3 frames of 816 bytes: 24 tilemap words (4 x 6, palette 2, tile numbers fixed in the file) + 24 4bpp
# tiles. $01:B0D8(name, 1, 1, x, y, 4, 6, frame, slot) decompresses the file and draws a frame; the tiles go to
# VRAM at the first tilemap tile number * 32, the tilemap to BG $E800 at (x, y). Palette: file FACEPAL (one
# palette), CGRAM row 2. Wrappers in bank $05 pick the frame: person * frames + expression (SHACHO: frame = company).
FACE_W, FACE_H = 4, 6
FRAME_BYTES = 816
FACE_FILES = [
    # file, wrapper, persons, expressions per person, group, label
    ("KAICHO", 0x879E, 3, 4, "会長", "会長"),
    ("SHACHO", 0x8715, 3, 1, "社長", "社長"),
    ("HISHO", 0x8768, 3, 3, "秘書", "秘書"),
    ("SHABU", 0x87CD, 3, 3, "部長", "SHABU 部長"),
    ("JINBU", 0x8803, 3, 3, "部長", "人事部長"),
    ("KEIBU", 0x8839, 3, 3, "部長", "経理部長"),
    ("BAIBU", 0x886F, 3, 3, "部長", "BAIBU 部長"),
    ("KOUBU", 0x88A5, 3, 3, "部長", "広告部長"),
    ("KAIBU", 0x88DB, 3, 3, "部長", "開発部長"),
    ("EIGBU", 0x8911, 3, 3, "部長", "営業部長"),
    ("SEIBU", 0x8947, 3, 3, "部長", "製造部長"),
]
FACE_NAME_ADDR = {"SHACHO": 0xD36B, "HISHO": 0xD372, "KAICHO": 0xD378, "SHABU": 0xD37F, "JINBU": 0xD385,
                  "KEIBU": 0xD38B, "BAIBU": 0xD391, "KOUBU": 0xD397, "KAIBU": 0xD39D, "EIGBU": 0xD3A3,
                  "SEIBU": 0xD3A9}   # $01:xxxx file-name strings pushed by the wrappers
FACE_TILEMAP = 0xE800           # VRAM byte address of the BG tilemap (32 wide)

# ---------------------------------------------------------------- maps
JAPANL_W, JAPANL_H, JAPANL_TILE0 = 28, 24, 0xA0      # palette 32 B + tilemap 28 x 24 + 188 tiles (tile 0xA0..)
JAPANS_W, JAPANS_H, JAPANS_TILE0 = 18, 22, 0x3C      # palette 32 B + tilemap 18 x 22 + 396 tiles (tile 0x3C..)


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
        self._lz = {}

    # ------------------------------------------------------------ basics
    def b1(self, addr: int) -> int:
        return lorom(0x01, addr)

    def ptr(self, o: int) -> int:
        d = self.data
        return lorom(d[o + 2], d[o] | d[o + 1] << 8)

    def cstr(self, o: int) -> str:
        d = self.data
        return d[o:d.index(b"\0", o)].decode("cp932")

    def strings(self, addr: int, n: int, bank: int = 0x01) -> list[str]:
        o = lorom(bank, addr)
        return [self.cstr(self.ptr(o + 3 * i)) for i in range(n)]

    def files(self) -> list[dict]:
        out, o, d = [], FILE_TABLE, self.data
        while d[o]:
            addr, bank = le16(d, o + 8), le16(d, o + 10)
            out.append({"index": len(out), "name": d[o:o + 8].split(b"\0")[0].decode("ascii"), "bank": bank,
                        "addr": addr, "offset": lorom(bank, addr), "size": int.from_bytes(d[o + 12:o + 16], "little")})
            o += 16
        return out

    def file(self, name: str) -> dict:
        return next(f for f in self.files() if f["name"] == name)

    def raw(self, name: str) -> bytes:
        f = self.file(name)
        return self.data[f["offset"]:f["offset"] + f["size"]]

    def lz(self, name: str) -> bytes:
        if name not in self._lz:
            self._lz[name] = koei_lz.decompress(self.data, self.file(name)["offset"], self.lz_tables)[0]
        return self._lz[name]

    def lz_size(self, f: dict) -> int | None:
        """Decompressed size of a file, None when it is not a KOEI LZ stream."""
        try:
            return len(koei_lz.decompress(self.data, f["offset"], self.lz_tables)[0])
        except (ValueError, IndexError):
            return None

    # ------------------------------------------------------------ prefectures
    def prefectures(self) -> list[dict]:
        d = self.data
        names = self.strings(PREF_NAME, PREF_COUNT)
        pop, sxy, mxy = self.b1(PREF_POP), self.b1(PREF_SMALL_XY), self.b1(PREF_MAP_XY)
        shapes = self.pref_shapes()
        out = []
        for i in range(PREF_COUNT):
            out.append({"index": i, "code": i + 1, "name": names[i],
                        "population": [le16(d, pop + 94 * k + 2 * i) for k in range(POP_PERIODS)],
                        "xy_cbad": (le16(d, sxy + 4 * i), le16(d, sxy + 4 * i + 2)),
                        "map_xy": (le16(d, mxy + 4 * i), le16(d, mxy + 4 * i + 2)),
                        "spans": shapes[i]})
        return out

    def pref_shapes(self) -> list[list[tuple[int, int, int, int]]]:
        """Per prefecture the runs that fill it on the JAPANS image ($13:EAEE colours them): (x, y, len, vertical);
        a record is count byte, direction byte (0 horizontal, 1 vertical), count x (x, y, len)."""
        d, o, out = self.data, self.b1(PREF_SHAPE), []
        for _ in range(PREF_COUNT):
            n, v = d[o], d[o + 1]
            out.append([(*d[o + 2 + 3 * k:o + 5 + 3 * k], v) for k in range(n)])
            o += 2 + 3 * n
        return out

    def population(self, start_year: int) -> list[int]:
        """WRAM $4417 after the game start ($07:A403): the record of the start year's period."""
        k = sum(start_year >= y for y in POP_YEAR_LIMITS)
        o = self.b1(PREF_POP) + 94 * k
        return [le16(self.data, o + 2 * i) for i in range(PREF_COUNT)]

    def hq_pairs(self) -> list[tuple[int, int]]:
        """$06:8AE1: in PRESENT MODE each company draws r1 = random 0..14 and r2 = random 0..1; its home prefecture
        ($2822) is pair[r1][r2] and its offices ($3638 mask) are both prefectures of the pair (1-based codes)."""
        o = self.b1(HQ_PAIRS)
        return [(le16(self.data, o + 4 * i), le16(self.data, o + 4 * i + 2)) for i in range(15)]

    # ------------------------------------------------------------ scenarios, companies, other tables
    def scenarios(self) -> list[dict]:
        names = self.strings(SCENARIO_NAME, SCENARIO_COUNT + FREE_COUNT)
        years = self.scenario_years()
        desc = self.scenario_descriptions()
        out = []
        for i in range(SCENARIO_COUNT + FREE_COUNT):
            free = i >= SCENARIO_COUNT
            y = years[i] if not free else (FREE_LONG_YEARS if i == 8 else (None, None))
            out.append({"index": i, "mode": "FREE" if free else "PRESENT", "name": names[i],
                        "start_year": y[0], "end_year": y[1],
                        "description": desc[i] if not free else desc[6 if i < 8 else 7]})
        return out

    def scenario_years(self) -> list[tuple[int, int]]:
        """(start, end) of the 6 PRESENT MODE scenarios: immediates of the switch at $06:A4E3."""
        o = lorom(*SCENARIO_YEARS_CODE)
        pat = re.compile(rb"\xa9(..)\x8f\x12\x28\x7e\xa9(..)\x8f\x10\x28\x7e", re.DOTALL)
        return [(le16(m.group(1), 0), le16(m.group(2), 0)) for m in pat.finditer(self.data, o, o + 0x70)]

    def scenario_descriptions(self) -> list[str]:
        """Page text of the 6 PRESENT MODE scenarios, then of FREE MODE short / middle and long ($06:9973)."""
        o = lorom(*SCENARIO_DESC_CODE)
        d = self.data
        out = []
        for i in range(8):
            p = o + 31 * i
            assert d[p] == 0xF4 and d[p + 3] == 0xF4, hex(p)
            out.append(self.cstr(lorom(d[p + 1], le16(d, p + 4))))
        return out

    def companies(self) -> list[dict]:
        names = [self.cstr(lorom(*a)) for a in COMPANY_NAME]
        return [{"index": i, "name": names[i]} for i in range(COMPANY_COUNT)]

    def products(self) -> list[dict]:
        s = self.strings(PRODUCT_SHORT, PRODUCT_COUNT)
        e = self.strings(PRODUCT, PRODUCT_COUNT)
        j = self.strings(PRODUCT_JA, PRODUCT_COUNT)
        return [{"index": i, "short": s[i], "name": e[i], "name_ja": j[i]} for i in range(PRODUCT_COUNT)]

    def levels(self) -> list[str]:
        return self.strings(LEVEL, LEVEL_COUNT)

    def industries(self) -> list[str]:
        return self.strings(INDUSTRY, INDUSTRY_COUNT)

    def news(self) -> list[str]:
        return self.strings(NEWS, NEWS_COUNT)

    # ------------------------------------------------------------ faces
    def face_frames(self, name: str) -> int:
        return len(self.lz(name)) // FRAME_BYTES

    def face_frame(self, name: str, frame: int) -> bytes:
        return self.lz(name)[FRAME_BYTES * frame:FRAME_BYTES * (frame + 1)]

    def face_tilemap(self, name: str, frame: int) -> list[int]:
        f = self.face_frame(name, frame)
        return [le16(f, 2 * i) for i in range(FACE_W * FACE_H)]

    def face_tiles(self, name: str, frame: int) -> bytes:
        return self.face_frame(name, frame)[48:]

    def face_pixels(self, name: str, frame: int) -> list[list[int]]:
        """32 x 48 colour numbers, drawn through the frame's tilemap (flips honoured, none are used)."""
        tm = self.face_tilemap(name, frame)
        t0 = tm[0] & 0x3FF
        tiles = tiles4(self.face_tiles(name, frame), FACE_W * FACE_H)
        img = [[0] * (FACE_W * 8) for _ in range(FACE_H * 8)]
        for i, e in enumerate(tm):
            t = tiles[(e & 0x3FF) - t0]
            for y in range(8):
                for x in range(8):
                    v = t[7 - y if e & 0x8000 else y][7 - x if e & 0x4000 else x]
                    img[i // FACE_W * 8 + y][i % FACE_W * 8 + x] = v
        return img

    def face_palette(self) -> list[int]:
        b = self.raw("FACEPAL")
        return [le16(b, 2 * i) for i in range(16)]

    def face_rgb(self, name: str, frame: int) -> list[list[tuple[int, int, int]]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [[pal[v] for v in row] for row in self.face_pixels(name, frame)]

    def faces(self) -> list[dict]:
        """Every frame of the 11 face files: (file, frame, person, expression, group, label)."""
        out = []
        for name, _, persons, expr, group, label in FACE_FILES:
            assert self.face_frames(name) == persons * expr
            for frame in range(persons * expr):
                out.append({"file": name, "frame": frame, "person": frame // expr, "expression": frame % expr,
                            "group": group, "label": label})
        return out

    # ------------------------------------------------------------ maps
    def _map(self, name: str, w: int, h: int, tile0: int) -> list[list[tuple[int, int, int]]]:
        x = self.lz(name)
        pal = [bgr555_rgb(le16(x, 2 * i)) for i in range(16)]
        n0 = 32 + 2 * w * h
        tiles = tiles4(x[n0:], (len(x) - n0) // 32)
        img = [[(0, 0, 0)] * (8 * w) for _ in range(8 * h)]
        for i in range(w * h):
            e = le16(x, 32 + 2 * i)
            t = tiles[(e & 0x3FF) - tile0]
            for y in range(8):
                for xx in range(8):
                    v = t[7 - y if e & 0x8000 else y][7 - xx if e & 0x4000 else xx]
                    img[i // w * 8 + y][i % w * 8 + xx] = pal[v]
        return img

    def map_parts(self, name: str) -> tuple[bytes, list[int], bytes]:
        """(palette 32 B, tilemap words, tile bytes) of JAPANL / JAPANS."""
        w, h = (JAPANL_W, JAPANL_H) if name == "JAPANL" else (JAPANS_W, JAPANS_H)
        x = self.lz(name)
        return x[:32], [le16(x, 32 + 2 * i) for i in range(w * h)], x[32 + 2 * w * h:]

    def japan_large(self) -> list[list[tuple[int, int, int]]]:
        """JAPANL, 224 x 192: the relief map of the home / office selection (BG tilemap $E800 from cell (2, 3))."""
        return self._map("JAPANL", JAPANL_W, JAPANL_H, JAPANL_TILE0)

    def japan_small(self) -> list[list[tuple[int, int, int]]]:
        """JAPANS, 144 x 176: the prefecture outline map."""
        return self._map("JAPANS", JAPANS_W, JAPANS_H, JAPANS_TILE0)
