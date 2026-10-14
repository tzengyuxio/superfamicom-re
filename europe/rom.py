"""SFC 欧陸戦線 Europe Sensen (KOEI, 1992) ROM decoding.

Offsets are file offsets of the headerless 1.5 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
The LZ decompressor ($C0:9A96) is the shared one in tools/koei_lz.py. The game is written in C: services go
through JSL $C0:8000 (0x17 = memcpy through the MVN at $00:006C, 0x4C = LZ to $7F:8000), vprintf is $C1:286A.
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Europe Sensen (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")
LZ_TABLES = 0x9939                       # decompressor table block, routine at $C0:9A96
LZ_POINTERS = 0x14978                    # 650 long pointers ($C1:4978)
LZ_COUNT = 650

# Text: half-width kana (ESC K = katakana, the default at the start of a string; ESC H = hiragana), ASCII, and
# 2-byte codes for font glyphs (data/charset.txt). In katakana '-' is ー. In the menus the half-width glyphs of
# '[' '\' ']' are 年 月 日; in weapon names '$' is Ⅰ and "'" is Ⅱ (weapons screen).
# Font: 16x16 1bpp at FONT + 32 g, four 8x8 tiles TL TR BL BR ($C1:19C0).
TEXT_BASE = 0x8140
GLYPH_COUNT = 652
FONT = 0xA9000
HALF_FONT = 0xA8000                      # 128 half-width 8x16 glyphs
HALF_WIDTH_KANJI = {"[": "年", "\\": "月", "]": "日", "$": "Ⅰ", "'": "Ⅱ"}

# Nationality bits (person +9, weapon +3); names from the flags the game draws, not ROM strings
NATIONS = {0x01: "ドイツ", 0x02: "イタリア", 0x04: "アメリカ", 0x08: "イギリス", 0x10: "フランス", 0x20: "ソ連"}
AXIS_BITS = 0x03

# Scenarios: starting one copies its block (BLOCK_SIZE bytes) to WRAM $7E:2000 with service 0x17 ($C6:06xx).
SCENARIO_COUNT = 6
SCENARIO_MENU = 0x69CE4                  # 6 long pointers: "1 フランス侵攻戦  1940[ 5\10]" ...
SCENARIO_BLOCKS = [0x1513C, 0x17127, 0x19112, 0x1B0FD, 0x292EB, 0x2B2D6]
BLOCK_SIZE = 0x1FEB
BLOCK_WRAM = 0x2000
# Block header: +0 0x45, +1 map number, +2 year - 1940, +3 month, +4 day, +5 palette selector ($C1:0893)
GENERALS_AT, GENERAL_SIZE, GENERAL_SLOTS = 0x220, 22, 40     # slots 0-19 Axis, 20-39 Allies; +9 = FF empty
CITIES_AT, CITY_SIZE = 0x1B28, 58                            # until a record without a name
CITY_MAX = (BLOCK_SIZE - CITIES_AT) // CITY_SIZE             # 21: the table runs to the end of the block
CITY_SLOTS = 6                                               # garrison slots of a city
LEADERS = 0x1D218                        # 6 records in the general format: ヒトラー ... ワシレフスキー
LEADER_COUNT = 6
PERSON_COUNT = 94                        # person ids 0-93 appear in the scenarios, 94-99 are the leaders
BIOGRAPHIES = 0x6C8E5                    # 94 x 7 long pointers ($C6:C8E5): 7 lines per person id
BIO_LINES = 7

# Weapons ($C1:D2BC): 158 records of 14 bytes. The weapons screen ($CA:24A0) prints the name with $C1:195E and
# "%2d %2d %2d %2d %2d" ($CA:6433) with AP, AT, 防, 速, 射 = +7, +6, +8, +9, +12.
WEAPONS = 0x1D2BC
WEAPON_SIZE = 14
WEAPON_COUNT = 158
WEAPON_KINDS = ["歩兵", "自動車化歩兵", "装甲歩兵", "戦車・自走砲", "砲・対戦車砲", "工兵", "修理兵", "補給兵"]

# Faces: 120 portraits of 40x48 (5x6 4bpp tiles row-major, 960 bytes), LZ entry FACE_ENTRY + person id
# ($C2:0664); person n uses portrait n (no face code). 94-99 are the leaders, 100-119 have no person.
# All use CGRAM palette 11 (OBJ palette 3), ROM copy FACE_PALETTE.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
FACE_ENTRY = 87
FACE_COUNT = 120
FACE_PALETTE = 0x1E887

# Europe map (title menu and scenario menu background): 30x23 BG2 tilemap words at EUROPE_TILEMAP (placed at
# tile (1, 2) of the screen), 8x8 tiles of LZ entry EUROPE_CHR loaded at tile 0x20, CGRAM palette 2 =
# EUROPE_PALETTES[0] and [1] by turns (about 250 frames each; colours 1-4, the sea, swap places).
EUROPE_TILEMAP = 0x68EFE
EUROPE_W, EUROPE_H = 30, 23
EUROPE_CHR = 623
EUROPE_TILE0 = 0x20
EUROPE_PALETTES = (0x69B62, 0x69B82)

# Battle maps: one 40x40 map per map number m (scenario block +1), cells of 16x16 pixels on BG2 (16x16 tiles).
#   LZ entry MAP_CELLS + m: 1600 cell codes (row-major) -> BG tilemap word at MAP_WORDS + 0x110 m + 2 code ($C6:0AA8)
#   LZ entry MAP_TERRAIN + m: 1600 bytes copied to WRAM $7E:40C2; low nibble = terrain (TERRAIN_NAMES, $C3:1B16)
#   Tiles: metatile pool LZ entry MAP_POOL (160 x 128 bytes: 2x2 tiles, top row then bottom row); the map's list
#   at MAP_USES + 0x8C m (LE16 metatile numbers, FF ends, at most 70) is loaded to BG tile t, t+1, t+16, t+17
#   for t = 2, 4, ... skipping each 16-tile row of bottom halves ($C6:05A0).
#   Palette: CGRAM palette 2 = MAP_PALETTE_BASE[m == 4] + 64 s, s = LE16 at PALETTE_SELECT + 2 * block[+5]
#   ($C1:0893; every scenario has s = 3). Some runs show the next palette (+32) instead (see docs: unsolved).
MAP_CELLS = 11
MAP_TERRAIN = 5
MAP_POOL = 17
MAP_WORDS = 0x1E10F
MAP_USES = 0x6897F
MAP_USE_MAX = 70
MAP_SIZE = 40
MAP_COUNT = 6
PALETTE_SELECT = 0x1492C
MAP_PALETTE_BASE = (0x146AC, 0x147EC)    # map 4 (バルジ, winter) uses the second
TERRAIN_NAMES = ["進入不可", "都市", "道路", "平地", "砂漠", "川", "湿地", "荒地", "森林", "丘陵", "橋"]   # $C1:E017


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


def glyph_address(code: int) -> int:
    """CPU address of the 32 glyph bytes $C1:19C0 copies for a 2-byte code: codes up to 0x8460 are 0x8140 + g,
    codes below 0x89F0 draw glyph 0, higher codes become 0x8200 + ((code - 0x89F0) << 8) first (16 bits); the
    address is $CA:(0x9000 + 32 (code - 0x8140)), the offset in 16 bits (the bank never carries)."""
    if code >= 0x89F0:
        code = (((code - 0x89F0) << 8) + 0x8200) & 0xFFFF
    elif code > 0x8460:
        code = 0x8140
    return 0xCA0000 | (0x9000 + ((code - 0x8140) << 5)) & 0xFFFF


def glyph_number(code: int) -> int:
    """Font glyph g (at FONT + 32 g) drawn for a 2-byte code; -1 if the address is outside the font."""
    g = (glyph_address(code) - 0xC00000 - FONT) // 32
    return g if 0 <= g < GLYPH_COUNT else -1


def nations(bits: int) -> str:
    return "・".join(n for b, n in NATIONS.items() if bits & b)


def kana_text(run: bytes, kata: bool) -> str:
    s = unicodedata.normalize("NFKC", run.decode("cp932", "replace"))
    if kata:
        s = s.replace("-", "ー")
    else:
        s = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)
    return "".join(HALF_WIDTH_KANJI.get(c, c) for c in s)


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
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    def text(self, raw: bytes, kata: bool = True) -> tuple[str, bool]:
        """Game text -> (str, kana mode at the end). NUL ends; ESC K / ESC H switch katakana / hiragana."""
        out, run = [], bytearray()

        def flush() -> None:
            if run:
                out.append(kana_text(bytes(run), kata))
                run.clear()

        i = 0
        while i < len(raw) and raw[i]:
            b = raw[i]
            if b == 0x1B and i + 1 < len(raw):
                flush()
                if raw[i + 1] in b"KH":
                    kata = raw[i + 1] == ord("K")
                i += 2
            elif (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC) and i + 1 < len(raw):
                flush()
                g = glyph_number(b << 8 | raw[i + 1])
                out.append(self.charset[g] if g >= 0 else f"{{{b:02X}{raw[i + 1]:02X}}}")
                i += 2
            else:
                run.append(b)
                i += 1
        flush()
        return "".join(out), kata

    def string(self, at: int, limit: int = 80) -> str:
        return self.text(self.data[at:at + limit])[0]

    # --- scenarios ---
    def block(self, sc: int) -> bytes:
        return self.data[SCENARIO_BLOCKS[sc]:SCENARIO_BLOCKS[sc] + BLOCK_SIZE]

    def scenarios(self) -> list[dict]:
        """Menu title and the block header (map, date) of the 6 scenarios."""
        out = []
        for sc in range(SCENARIO_COUNT):
            line = self.string(self.ptr(SCENARIO_MENU + 3 * sc))
            b = self.block(sc)
            out.append({"id": sc + 1, "title": line.split()[1], "menu": line, "map": b[1], "year": 1940 + b[2],
                        "month": b[3], "day": b[4], "header": b[:16]})
        return out

    @staticmethod
    def general(r: bytes, slot: int | None = None) -> dict:
        """22 bytes: +0 name (9, half-width katakana, NUL / space padded), +9 nationality bits, +10 指揮,
        +11 魅力, +12 unknown, +13 / +14 unknown (equal), +15 歩兵, +16 砲兵, +17 戦車, +18 経験, +19 unknown,
        +20 person id, +21 unknown (leaders: 04 / 05)."""
        return {"slot": slot, "raw": r, "name": kana_text(r[:9].split(b"\0")[0], True).strip(), "nation": r[9],
                "指揮": r[10], "魅力": r[11], "unknown12": r[12], "unknown13": r[13], "unknown14": r[14],
                "歩兵": r[15], "砲兵": r[16], "戦車": r[17], "経験": r[18], "unknown19": r[19], "id": r[20],
                "unknown21": r[21]}

    def generals(self, sc: int) -> list[dict]:
        """Occupied general slots of the scenario (0-19 Axis, 20-39 Allies)."""
        b = self.block(sc)
        out = []
        for k in range(GENERAL_SLOTS):
            o = GENERALS_AT + GENERAL_SIZE * k
            if b[o + 9] != 0xFF:
                out.append(self.general(b[o:o + GENERAL_SIZE], k))
        return out

    def leaders(self) -> list[dict]:
        return [self.general(self.data[LEADERS + GENERAL_SIZE * k:LEADERS + GENERAL_SIZE * (k + 1)], k)
                for k in range(LEADER_COUNT)]

    def persons(self) -> list[dict]:
        """Person ids 0-99: the record of each id's first scenario (the records of an id are the same in every
        scenario), then the leaders; with the scenarios (1-6) each id appears in."""
        seen: dict[int, dict] = {}
        for sc in range(SCENARIO_COUNT):
            for g in self.generals(sc):
                p = seen.setdefault(g["id"], dict(g, scenarios=[], side=[]))
                p["scenarios"].append(sc + 1)
                p["side"].append("枢軸" if g["slot"] < 20 else "連合")
        for g in self.leaders():
            seen[g["id"]] = dict(g, scenarios=[], side=["枢軸" if g["nation"] & AXIS_BITS else "連合"])
        return [seen[k] for k in sorted(seen)]

    def biography(self, pid: int) -> list[str]:
        """The 7 lines of person pid (0-93) shown on the ability review screen; the kana mode carries over."""
        lines, kata = [], True
        for k in range(BIO_LINES):
            s, kata = self.text(self.data[self.bio_pointer(pid, k):][:120], kata)
            lines.append(s)
        return lines

    def bio_pointer(self, pid: int, line: int) -> int:
        return self.ptr(BIOGRAPHIES + 3 * (BIO_LINES * pid + line))

    def cities(self, sc: int) -> list[dict]:
        """58 bytes: +0 name (11), +11 x, +12 y (map cell), +13 弾薬 +15 燃料 +17 食料 (LE16, the city screen's
        three icons; names in the order of the labels "弾薬 %5d 燃料 %5d 食料 %5d" at 0x7D017), +19 +21 +23 the
        same three again (unknown: maximum or start value), +25 耐久, +26 耐久 maximum, +27 6 garrison slots of 5 bytes: weapon id (FF none), count LE16,
        2 unknown bytes, +57 flags: bit 4 side (1 連合, 0 枢軸; $C3:0694), bit 6 unknown (tested by the city
        screen at $CA:12AB), the rest unknown."""
        b = self.block(sc)
        out = []
        for k in range(CITY_MAX):
            o = CITIES_AT + CITY_SIZE * k
            r = b[o:o + CITY_SIZE]
            name = self.text(r[:11])[0]
            if not name:
                break
            garrison = []
            for j in range(CITY_SLOTS):
                g = r[27 + 5 * j:32 + 5 * j]
                if g[0] != 0xFF:
                    garrison.append({"weapon": g[0], "count": le16(g, 1), "unknown": g[3:5]})
            out.append({"id": k, "raw": r, "name": name, "x": r[11], "y": r[12],
                        "弾薬": le16(r, 13), "燃料": le16(r, 15), "食料": le16(r, 17),
                        "values2": [le16(r, 19), le16(r, 21), le16(r, 23)], "耐久": r[25], "耐久max": r[26],
                        "garrison": garrison, "flags": r[57], "side": "連合" if r[57] & 0x10 else "枢軸"})
        return out

    # --- weapons ---
    def weapons(self) -> list[dict]:
        """14 bytes: +0 name (long pointer), +3 nationality bits, +4 available from (inferred: high nibble year
        - 1940, low nibble month; 0 = from the start), +5 kind (WEAPON_KINDS), +6 AT, +7 AP, +8 防, +9 速,
        +10 +11 unknown, +12 射 (range), +13 unknown."""
        out = []
        for i in range(WEAPON_COUNT):
            r = self.data[WEAPONS + WEAPON_SIZE * i:WEAPONS + WEAPON_SIZE * (i + 1)]
            out.append({"id": i, "raw": r, "name": self.string(self.ptr(WEAPONS + WEAPON_SIZE * i), 24),
                        "nation": r[3], "available": r[4], "kind": r[5], "AT": r[6], "AP": r[7], "防": r[8],
                        "速": r[9], "unknown10": r[10], "unknown11": r[11], "射": r[12], "unknown13": r[13]})
        return out

    # --- faces ---
    def face_tiles(self, n: int) -> bytes:
        return self.entry(FACE_ENTRY + n)[:FACE_BYTES]

    def face_palette(self) -> list[int]:
        return [le16(self.data, FACE_PALETTE + 2 * i) for i in range(16)]

    def face_pixels(self, n: int) -> list[int]:
        """40x48 colour numbers of portrait n, row-major."""
        return tiles_pixels(self.face_tiles(n), FACE_W, FACE_H)

    def face_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(n)]

    # --- Europe map ---
    def europe_tilemap(self) -> list[int]:
        return [le16(self.data, EUROPE_TILEMAP + 2 * i) for i in range(EUROPE_W * EUROPE_H)]

    def europe_palette(self) -> list[int]:
        return [le16(self.data, EUROPE_PALETTES[0] + 2 * i) for i in range(16)]

    def europe_rgb(self) -> tuple[int, int, list[tuple[int, int, int]]]:
        chr_ = bytearray(0x10000)
        tiles = self.entry(EUROPE_CHR)
        chr_[32 * EUROPE_TILE0:32 * EUROPE_TILE0 + len(tiles)] = tiles
        pal = [bgr555_rgb(c) for c in self.europe_palette()]
        w, h = EUROPE_W * 8, EUROPE_H * 8
        out = [pal[0]] * (w * h)
        for i, word in enumerate(self.europe_tilemap()):
            draw_tile(out, w, i % EUROPE_W * 8, i // EUROPE_W * 8, chr_, word, 8, pal)
        return w, h, out

    # --- battle maps ---
    def map_cells(self, m: int) -> bytes:
        return self.entry(MAP_CELLS + m)

    def map_terrain(self, m: int) -> list[int]:
        """1600 terrain numbers (TERRAIN_NAMES), row-major."""
        return [v & 15 for v in self.entry(MAP_TERRAIN + m)]

    def map_terrain_flags(self, m: int) -> list[int]:
        """High nibble of the terrain bytes (0 or 8 in the ROM; unknown)."""
        return [v >> 4 for v in self.entry(MAP_TERRAIN + m)]

    def map_words(self, m: int) -> list[int]:
        """1600 BG tilemap words (16x16 tiles) as $C6:0AA8 writes them."""
        return [le16(self.data, MAP_WORDS + 0x110 * m + 2 * c) for c in self.map_cells(m)]

    def map_uses(self, m: int) -> list[int]:
        out = []
        for i in range(MAP_USE_MAX):
            v = le16(self.data, MAP_USES + 0x8C * m + 2 * i)
            if v & 0xFF == 0xFF:
                break
            out.append(v)
        return out

    def map_chr(self, m: int) -> bytes:
        """BG2 character data (from VRAM byte 0x8000) as the loader builds it: metatile k of the map's list at
        tile t (top) and t + 16 (bottom)."""
        pool = self.entry(MAP_POOL)
        out = bytearray(0x8000)
        t = 2
        for mt in self.map_uses(m):
            src = pool[128 * mt:128 * mt + 128]
            out[32 * t:32 * t + 64] = src[:64]
            out[32 * (t + 16):32 * (t + 16) + 64] = src[64:]
            t += 2
            if t % 16 == 0:
                t += 16
        return bytes(out)

    def map_palette_offset(self, m: int, sc: int | None = None) -> int:
        b5 = self.block(sc)[5] if sc is not None else 0
        s = le16(self.data, PALETTE_SELECT + 2 * b5)
        return MAP_PALETTE_BASE[m == 4] + 64 * s

    def map_palette(self, m: int) -> list[int]:
        base = self.map_palette_offset(m)
        return [le16(self.data, base + 2 * i) for i in range(16)]

    def map_rgb(self, m: int) -> tuple[int, int, list[tuple[int, int, int]]]:
        """640x640 picture of map m."""
        return render_words(self.map_words(m), MAP_SIZE, self.map_chr(m),
                            {2: [bgr555_rgb(c) for c in self.map_palette(m)]})


def tiles_pixels(tiles: bytes, w: int, h: int) -> list[int]:
    out = [0] * (w * h * 64)
    for t in range(w * h):
        for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
            out[(t // w * 8 + i // 8) * w * 8 + t % w * 8 + i % 8] = v
    return out


def draw_tile(out: list, width: int, x0: int, y0: int, chr_: bytes, word: int, size: int, pal) -> None:
    """Draw a BG tilemap word (tile number from chr_ byte 0, 8x8 or 16x16) into a row-major RGB list.
    pal: 16 colours, or {palette number: 16 colours}."""
    n, p, hf, vf = word & 0x3FF, word >> 10 & 7, word >> 14 & 1, word >> 15
    colours = pal[p] if isinstance(pal, dict) else pal
    cache: dict[int, list[int]] = {}
    for y in range(size):
        yy = size - 1 - y if vf else y
        for x in range(size):
            xx = size - 1 - x if hf else x
            t = n + xx // 8 + 16 * (yy // 8)
            if t not in cache:
                cache[t] = decode_tile(chr_[32 * t:32 * t + 32])
            out[(y0 + y) * width + x0 + x] = colours[cache[t][(yy % 8) * 8 + xx % 8]]


def render_words(words: list[int], cols: int, chr_: bytes, pal) -> tuple[int, int, list[tuple[int, int, int]]]:
    """Picture of a grid of 16x16 BG tilemap words."""
    rows = len(words) // cols
    w, h = cols * 16, rows * 16
    out = [(0, 0, 0)] * (w * h)
    for i, word in enumerate(words):
        draw_tile(out, w, i % cols * 16, i // cols * 16, chr_, word, 16, pal)
    return w, h, out
