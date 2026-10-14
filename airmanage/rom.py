"""SFC エアーマネージメント 大空に賭ける (KOEI) ROM decoding.

Headerless 1 MB LoROM image, no compression. Everything lives in named files (file table at 0x7000, as in
武将風雲録). The game is C compiled to KOEI's p-code: the modules are loaded to WRAM bank $7E and their
tables are addressed by p-code (WRAM) address, so module data is read here by p-code address.

Both the original release and Rev 1 are supported: Rev 1 moves most files (read through the file table) and
its ALNMAIN is 6 bytes longer, which shifts the ALNMAIN tables by +6. See airmanage/docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROMS = os.path.join(os.path.dirname(HERE), "roms")
DEFAULT_ROM = os.path.join(ROMS, "Air Management - Oozora ni Kakeru (Japan).zip")
REV1_ROM = os.path.join(ROMS, "Air Management - Oozora ni Kakeru (Japan) (Rev 1).zip")
KANJI_FILE = os.path.join(HERE, "data", "kanji.txt")

FILE_TABLE = 0x7000             # 16-byte entries: name[8], bank LE16, addr LE16, size LE32; name[0] = 0 ends

# ---------------------------------------------------------------- modules
# p-code address of a module's first byte (the loader copies the file there in bank $7E)
LOAD = {"ALNMAIN": 0x2000, "OPENING": 0x9000, "COMMAND": 0x8C00, "TRADE": 0xD000, "DIORMINF": 0xD000}
ALNMAIN_SIZE = 0x3BF0           # original; Rev 1 is 0x3BF6 and its tables sit 6 bytes later

# ALNMAIN tables (p-code addresses in the original release)
CITY_COUNT = 22
DISTANCE = 0x489D               # 22 x 22 LE16, km / 10, diagonal FFFF; row = from, column = to
MATRIX2 = 0x4C65                # 22 x 22 LE16, symmetric, zero diagonal (unsolved)
CITY_TYPE = 0x502D              # 22 LE16: 0 ミリオン 1 ビジネス 2 リゾ－ト 3 バランス
CITY_KANA = 0x5059              # 22 pointers: half-width city name
CITY_NAME = 0x510D              # 22 pointers: full-width city name
AIRLINE = 0x5209                # 22 pointers: default airline name per home city
AIRPORT = 0x52E5                # 22 pointers: airport name
CITY_XY = 0x53A1                # 22 x (x, y) LE16: city on the 256 x 256 world map (ALMAPE)
MONTHS = 0x53F9                 # 12 pointers
MAKER_COLOR = 0x5441            # 5 LE16 BGR555, the maker's colour in the trade screen
AIRCRAFT = 0x544B               # 20 x 16 bytes, see aircraft()
AIRCRAFT_COUNT = 20
MAKER_FACE = 0x5649             # 5 x 4 bytes: kind LE16, image, palette (face descriptor)
CITY_ROUTES = 0x565D            # 22 x 3 x (city LE16, byte, byte) (guess: start routes)
MAKER_NAME = 0x5765             # 5 pointers
AIRLINE2 = 0x5799               # 22 pointers: second airline name set (unsolved)
AIRCRAFT_GFX = 0x590E           # 20 x (L_ picture LE16, LW_ picture LE16 or FFFF)
AIRCRAFT_ASCII = 0x597C         # 20 pointers: lower-case ASCII model name
WORLD_XY = 0x5A40               # 22 x (x, y) LE16 (unsolved: a larger world coordinate)
DIFFICULTY = 0x4868             # 4 pointers
# Aircraft per maker: TRADE $D0A8 switch (first record, count); maker 4 (ワールドリース) sells none
MAKER_AIRCRAFT = [(0, 6), (6, 5), (11, 4), (15, 4), (0, 0)]
# DIORMINF $DBA3: pointers 現在、 / 都市として発展しています。 / 4 city type names (index = CITY_TYPE + 2)
CITY_TYPE_NAMES = 0xDBA7

# OPENING tables (same address in both releases)
SCENARIO_CITY = 0xB9B8          # 2 scenarios x 22 cities x 5 LE16
SCENARIO_HQ = 0xBB70            # 22 x 4 LE16 copied to the player record +18 (unsolved)
SCENARIO_FUNDS = 0xBC20         # 2 scenarios x 22 LE32: starting funds (万$) by home city
SCENARIOS = [("シナリオ1", 1963), ("シナリオ2", 1983)]  # start year: $4682 shown as 1963 / 1983 (screen)

# TRADE: 6 pointers to the fuel-cost rank letters (ｓ ｓ ａ ｂ ｃ ｄ), index fuel // 20
TRADE_RANK = 0xE9C2

# ---------------------------------------------------------------- faces
# 40 x 48 = 5 x 6 4bpp tiles row-major, 960 bytes; palettes: file PAL_M, 12 x 16 colours.
# A face is drawn from a 4-byte descriptor (kind LE16, image, palette): kind 0 MANAGER (aide),
# 1 PERSON (negotiation partner), 2 MAKER. Eye and mouth animation frames in EYE_* / MOUTH_* (288 bytes each).
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
FACE_KINDS = [("MANAGER", 8, "部下"), ("PERSON", 20, "交渉相手"), ("MAKER", 5, "メーカー")]
# OPENING $A6EE: the player's aide (main-screen advisor) by home city (image, palette);
# $A7A7: partners image base + r, palette base + r // 2
MANAGER_PALETTE = [0, 2, 3, 4, 5, 6, 8, 8]

# ---------------------------------------------------------------- text and font
# Shift-JIS. Full-width glyphs (COMMON lookup at $00:BCAA): 16x16 = 4 2bpp tiles (TL TR BL BR), 64 bytes;
# digits are 8x16 (2 tiles, 32 bytes). Glyph address = base + index * size, linear in the ROM file.
SYMBOLS = 0x41E4                # 22 SJIS codes (LE16) in bank 0
KANJI = 0x4210                  # 437 SJIS codes (LE16) in bank 0
SYMBOL_COUNT, KANJI_COUNT = 22, 437
GLYPH_BASE = {"symbol": 0x9920, "digit": 0x9EA0, "alpha": 0xA000, "hiragana": 0xBC40, "katakana": 0xA680,
              "kanji": 0xD100}  # WRAM $0CAA-$0CB4 (bank 1 addresses = file offsets)
HALF_FONT = 0x8ED0              # FONT file: first 165 8x8 2bpp tiles are the half-width font

# ---------------------------------------------------------------- world map
# ALMAPE: palette (16 colours), 32 x 32 tilemap (tile n palette 1), 1024 4bpp tiles; the main screen and the
# home-city screen show it (main screen: BG palette 1, scrolled so that the home city is centred).
MAP_W = MAP_H = 32


def lorom(bank: int, addr: int) -> int:
    return (bank & 0x7F) * 0x8000 + (addr & 0x7FFF)


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]  # drop a 512-byte copier header if present


def decode_tile(raw: bytes) -> list[int]:
    """One 4bpp SNES tile (32 bytes) -> 64 colour numbers, row-major."""
    out = []
    for y in range(8):
        p0, p1, p2, p3 = raw[2 * y], raw[2 * y + 1], raw[16 + 2 * y], raw[17 + 2 * y]
        for x in range(7, -1, -1):
            out.append((p0 >> x & 1) | (p1 >> x & 1) << 1 | (p2 >> x & 1) << 2 | (p3 >> x & 1) << 3)
    return out


def decode_tile_2bpp(raw: bytes) -> list[int]:
    out = []
    for y in range(8):
        p0, p1 = raw[2 * y], raw[2 * y + 1]
        for x in range(7, -1, -1):
            out.append((p0 >> x & 1) | (p1 >> x & 1) << 1)
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    """SNES colour -> 8-bit RGB (5-bit value << 3 | value >> 2, as Mesen shows it)."""
    return tuple((c >> s & 31) << 3 | (c >> s & 31) >> 2 for s in (0, 5, 10))


def load_kanji(path: str = KANJI_FILE) -> str:
    with open(path, encoding="utf-8") as f:
        s = "".join(line.rstrip("\n") for line in f if not line.startswith("#"))
    assert len(s) == KANJI_COUNT, len(s)
    return s


def sjis(code: int) -> str:
    return code.to_bytes(2, "big").decode("cp932")


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self._files = {f["name"]: f for f in self.files()}
        self.aln = self.file("ALNMAIN")
        self.aln_shift = len(self.aln) - ALNMAIN_SIZE
        assert self.aln_shift in (0, 6), hex(len(self.aln))
        assert self.u16_at("ALNMAIN", DISTANCE) == 0xFFFF and self.u16_at("ALNMAIN", DISTANCE + 2) != 0xFFFF
        self.rev = 1 if self.aln_shift else 0

    # ------------------------------------------------------------ files and module data

    def files(self) -> list[dict]:
        out = []
        for o in range(FILE_TABLE, FILE_TABLE + 0x1000, 16):
            e = self.data[o:o + 16]
            if not e[0]:
                break
            bank, addr = le16(e, 8), le16(e, 10)
            out.append({"name": e[:8].split(b"\0")[0].decode("ascii"), "bank": bank, "addr": addr,
                        "offset": lorom(bank, addr), "size": int.from_bytes(e[12:16], "little")})
        return out

    def file(self, name: str) -> bytes:
        f = self._files[name]
        return self.data[f["offset"]:f["offset"] + f["size"]]

    def offset(self, module: str, addr: int) -> int:
        """ROM file offset of p-code address addr in module (ALNMAIN data addresses are given for the original)."""
        f = self._files[module]
        shift = self.aln_shift if module == "ALNMAIN" else 0
        return f["offset"] + addr + shift - LOAD[module]

    def u16_at(self, module: str, addr: int) -> int:
        return le16(self.data, self.offset(module, addr))

    def words(self, module: str, addr: int, n: int) -> list[int]:
        o = self.offset(module, addr)
        return [le16(self.data, o + 2 * i) for i in range(n)]

    def cstr(self, module: str, ptr: int) -> str:
        """Zero-terminated Shift-JIS string at p-code address ptr (a pointer value: no Rev 1 shift)."""
        f = self._files[module]
        o = f["offset"] + ptr - LOAD[module]
        return self.data[o:self.data.index(b"\0", o)].decode("cp932")

    def strings(self, module: str, table: int, n: int) -> list[str]:
        return [self.cstr(module, p) for p in self.words(module, table, n)]

    # ------------------------------------------------------------ cities

    def cities(self) -> list[dict]:
        names = self.strings("ALNMAIN", CITY_NAME, CITY_COUNT)
        kana = self.strings("ALNMAIN", CITY_KANA, CITY_COUNT)
        airports = self.strings("ALNMAIN", AIRPORT, CITY_COUNT)
        airlines = self.strings("ALNMAIN", AIRLINE, CITY_COUNT)
        airlines2 = self.strings("ALNMAIN", AIRLINE2, CITY_COUNT)
        types = self.words("ALNMAIN", CITY_TYPE, CITY_COUNT)
        type_names = self.city_type_names()
        xy = self.words("ALNMAIN", CITY_XY, 2 * CITY_COUNT)
        wxy = self.words("ALNMAIN", WORLD_XY, 2 * CITY_COUNT)
        o = self.offset("ALNMAIN", CITY_ROUTES)
        out = []
        for i in range(CITY_COUNT):
            r = self.data[o + 12 * i:o + 12 * i + 12]
            out.append({"index": i, "name": names[i], "kana": kana[i], "airport": airports[i],
                        "airline": airlines[i], "airline2": airlines2[i], "type": types[i],
                        "type_name": type_names[types[i]], "map_x": xy[2 * i], "map_y": xy[2 * i + 1],
                        "world_x": wxy[2 * i], "world_y": wxy[2 * i + 1],
                        "routes": [(le16(r, 4 * k), r[4 * k + 2], r[4 * k + 3]) for k in range(3)]})
        return out

    def city_type_names(self) -> list[str]:
        return self.strings("DIORMINF", CITY_TYPE_NAMES, 4)

    def distances(self) -> list[list[int | None]]:
        """km between cities (None on the diagonal)."""
        w = self.words("ALNMAIN", DISTANCE, CITY_COUNT * CITY_COUNT)
        return [[None if w[22 * a + b] == 0xFFFF else w[22 * a + b] * 10 for b in range(22)] for a in range(22)]

    def matrix2(self) -> list[list[int]]:
        w = self.words("ALNMAIN", MATRIX2, CITY_COUNT * CITY_COUNT)
        return [w[22 * a:22 * a + 22] for a in range(22)]

    # ------------------------------------------------------------ scenarios

    def scenario_cities(self, s: int) -> list[dict]:
        """OPENING $A929: the game copies v0-v2 to the city record $5BF2 + 12 * c (+2, +4, +6) and sets +10 =
        (2 * v1 + v2) // 3; v3 goes to the slot record $6DD6 + 20 * c (+2 byte); v4 is added to the used slots
        (+3) and to the player's slot count when c is that player's home city."""
        o = self.offset("OPENING", SCENARIO_CITY) + 220 * s
        funds = self.offset("OPENING", SCENARIO_FUNDS) + 88 * s
        out = []
        for c in range(CITY_COUNT):
            v = [le16(self.data, o + 10 * c + 2 * k) for k in range(5)]
            out.append({"city": c, "population": v[0] * 100, "pop_raw": v[0], "tourism": v[1],
                        "economy": v[2], "slots": v[3], "home_slots": v[4],
                        "funds": int.from_bytes(self.data[funds + 4 * c:funds + 4 * c + 4], "little"),
                        "raw": v})
        return out

    def hq_table(self, s: int | None = None) -> list[list[int]]:
        """4 values per home city copied to the player record +18..+25 (meaning unsolved). With s, as the game
        sets them for that scenario: scenario 1 lowers them by 15 / 15 / 15 / 30 (floor 5 / 5 / 5 / 0)."""
        o = self.offset("OPENING", SCENARIO_HQ)
        t = [[le16(self.data, o + 8 * c + 2 * k) for k in range(4)] for c in range(CITY_COUNT)]
        if s == 0:
            t = [[max(x - 15, 5) for x in v[:3]] + [max(v[3] - 30, 0)] for v in t]
        return t

    @staticmethod
    def rank(value: int) -> str:
        """Rank letter the city screen shows for 経済力 / 観光地 (DIORMINF $D41B: table d c b a s)."""
        return "dcbas"[(value - 1) // 20]

    def fuel_rank(self, fuel: int) -> str:
        """Rank letter the trade screen shows for 燃料費 (TRADE $E065: table at $E9C2, index fuel // 20)."""
        return self.cstr("TRADE", self.words("TRADE", TRADE_RANK, 6)[fuel // 20])

    # ------------------------------------------------------------ aircraft and makers

    def aircraft(self) -> list[dict]:
        o = self.offset("ALNMAIN", AIRCRAFT)
        ascii_names = self.strings("ALNMAIN", AIRCRAFT_ASCII, AIRCRAFT_COUNT)
        gfx = self.words("ALNMAIN", AIRCRAFT_GFX, 2 * AIRCRAFT_COUNT)
        maker = {k: m for m, (first, n) in enumerate(MAKER_AIRCRAFT) for k in range(first, first + n)}
        out = []
        for k in range(AIRCRAFT_COUNT):
            w = [le16(self.data, o + 16 * k + 2 * i) for i in range(8)]
            out.append({"index": k, "name": self.cstr("ALNMAIN", w[0]), "ascii": ascii_names[k],
                        "maker": maker.get(k), "seats": w[1], "range_km": w[2] * 10, "price": w[3],
                        "from_year": w[4], "until_year": None if w[5] == 2100 else w[5], "until_raw": w[5],
                        "fuel": w[6], "fuel_rank": self.fuel_rank(w[6]), "w14": w[7],
                        "picture": gfx[2 * k], "picture_wide": gfx[2 * k + 1]})
        return out

    def makers(self) -> list[dict]:
        names = self.strings("ALNMAIN", MAKER_NAME, 5)
        colors = self.words("ALNMAIN", MAKER_COLOR, 5)
        o = self.offset("ALNMAIN", MAKER_FACE)
        out = []
        for m in range(5):
            d = self.data[o + 4 * m:o + 4 * m + 4]
            first, n = MAKER_AIRCRAFT[m]
            out.append({"index": m, "name": names[m], "color": colors[m], "face_kind": le16(d, 0),
                        "face_image": d[2], "face_palette": d[3], "aircraft": list(range(first, first + n))})
        return out

    # ------------------------------------------------------------ faces

    def face_palette(self, p: int) -> list[int]:
        raw = self.file("PAL_M")[32 * p:32 * p + 32]
        return [le16(raw, 2 * i) for i in range(16)]

    def face_raw(self, kind: int, img: int) -> bytes:
        return self.file(FACE_KINDS[kind][0])[FACE_BYTES * img:FACE_BYTES * (img + 1)]

    def face_pixels(self, kind: int, img: int) -> list[list[int]]:
        raw = self.face_raw(kind, img)
        px = [[0] * (8 * FACE_W) for _ in range(8 * FACE_H)]
        for t in range(FACE_W * FACE_H):
            tile = decode_tile(raw[32 * t:32 * t + 32])
            for i, c in enumerate(tile):
                px[t // FACE_W * 8 + i // 8][t % FACE_W * 8 + i % 8] = c
        return px

    def default_palette(self, kind: int, img: int) -> int:
        """Palette the game pairs with the image (OPENING $A6EE / $A7A7, ALNMAIN maker descriptors)."""
        if kind == 0:
            return MANAGER_PALETTE[img]
        if kind == 1:
            return img // 2
        return self.makers()[img]["face_palette"]

    def face_rgb(self, kind: int, img: int, pal: int | None = None) -> list[list[tuple[int, int, int]]]:
        p = [bgr555_rgb(c) for c in self.face_palette(self.default_palette(kind, img) if pal is None else pal)]
        return [[p[c] for c in row] for row in self.face_pixels(kind, img)]

    def faces(self) -> list[dict]:
        out = []
        for kind, (name, n, label) in enumerate(FACE_KINDS):
            for img in range(n):
                out.append({"kind": kind, "file": name, "label": label, "image": img,
                            "palette": self.default_palette(kind, img)})
        return out

    # ------------------------------------------------------------ text and font

    def symbol_codes(self) -> list[int]:
        return [le16(self.data, SYMBOLS + 2 * i) for i in range(SYMBOL_COUNT)]

    def kanji_codes(self) -> list[int]:
        return [le16(self.data, KANJI + 2 * i) for i in range(KANJI_COUNT)]

    def glyph_address(self, code: int) -> tuple[int, int] | None:
        """(file offset, bytes) of the glyph the game draws for a full-width Shift-JIS code ($00:BCAA), None if
        the code is not in the font (the game then draws symbol 1, ■)."""
        if code < 0x824F:
            sym = self.symbol_codes()
            if code not in sym:
                return None
            return GLYPH_BASE["symbol"] + 64 * sym.index(code), 64
        if code < 0x825F:
            return GLYPH_BASE["digit"] + 32 * (code - 0x824F), 32
        if code < 0x829E:
            return GLYPH_BASE["alpha"] + 64 * (code - (0x8260 if code < 0x8280 else 0x8281)), 64
        if code < 0x833F:
            return GLYPH_BASE["hiragana"] + 64 * (code - 0x829F), 64
        if code < 0x839E:
            return GLYPH_BASE["katakana"] + 64 * (code - 0x8340), 64
        k = self.kanji_codes()
        if code not in k:
            return None
        return GLYPH_BASE["kanji"] + 64 * k.index(code), 64

    def glyph(self, code: int) -> list[list[int]]:
        """16 rows of 16 (8 for digits) colour numbers 0-3."""
        a, n = self.glyph_address(code)
        raw = self.data[a:a + n]
        tiles = [decode_tile_2bpp(raw[16 * t:16 * t + 16]) for t in range(n // 16)]
        w = 8 if n == 32 else 16
        return [[tiles[(y // 8) * (w // 8) + x // 8][y % 8 * 8 + x % 8] if n == 64 else tiles[y // 8][y % 8 * 8 + x]
                 for x in range(w)] for y in range(16)]

    def font_codes(self) -> list[int]:
        """All full-width codes the font covers, in glyph order of each set."""
        out = list(self.symbol_codes())
        out += range(0x824F, 0x8259)
        out += list(range(0x8260, 0x827A)) + list(range(0x8281, 0x829B))
        out += range(0x829F, 0x82F2)
        out += [c for c in range(0x8340, 0x8397) if c != 0x837F]
        out += self.kanji_codes()
        return out

    # ------------------------------------------------------------ world map

    def world_map(self) -> tuple[list[int], list[int], bytes]:
        """(16 palette colours, 32 x 32 tilemap entries, CHR) of ALMAPE."""
        raw = self.file("ALMAPE")
        return ([le16(raw, 2 * i) for i in range(16)], [le16(raw, 0x20 + 2 * i) for i in range(MAP_W * MAP_H)],
                raw[0x820:])

    def world_map_pixels(self) -> list[list[int]]:
        """256 x 256 colour numbers 0-15 (colour 0 is the backdrop)."""
        _, tm, chr_ = self.world_map()
        px = [[0] * (8 * MAP_W) for _ in range(8 * MAP_H)]
        for i, e in enumerate(tm):
            t = decode_tile(chr_[32 * (e & 0x3FF):32 * (e & 0x3FF) + 32])
            hf, vf = e >> 14 & 1, e >> 15 & 1
            for k, c in enumerate(t):
                x, y = k % 8, k // 8
                px[i // MAP_W * 8 + (7 - y if vf else y)][i % MAP_W * 8 + (7 - x if hf else x)] = c
        return px
