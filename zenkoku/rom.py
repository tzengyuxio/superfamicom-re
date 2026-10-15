"""SFC スーパー信長の野望・全国版 (KOEI) ROM decoding.

Offsets are file offsets of the headerless 512 KB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
The LZ decompressor ($C0:A02B) is the shared one in tools/koei_lz.py. The program is compiled C (stack
arguments, a service dispatcher at $C0:8000).
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Super Nobunaga no Yabou - Zenkoku Ban (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")
LZ_TABLES = 0x9ECE                      # decompressor tables ($C0:9ECE), routine at $C0:A02B
LZ_POINTERS, LZ_COUNT = 0x3D133, 193    # 3-byte pointers ($C3:D133)

# ---------------------------------------------------------------- text
# Two-byte codes 0x8140 + g draw glyph g of the 16x16 font (1bpp, 32 bytes at FONT + 32 g, 8x8 tiles in the
# order TL TR BL BR; $C3:339A). A code whose low byte would be 00 is written 0x9140 + k (= 0x8200 + 0x100 k).
# Other bytes are half-width (ASCII digits and letters, JIS X 0201 kana shown as hiragana).
FONT = 0x0000
GLYPH_COUNT = 636
CODE_BASE = 0x8140
ZERO_ESCAPE = 0x9140
LIGATURES = {(0x83B9, 0x83BA, 0x83BB): "長宗我部"}   # 3 glyphs (633-635) for the 4-character surname
HALF_FONT = 0x4F60                      # 8x16 half-width glyphs, 16 bytes each (digit d is glyph 79 + d)
HALF_DIGIT0 = 79

# ---------------------------------------------------------------- scenarios
# The scenario loader ($C7:9DA0) copies one block to $7E:2000 and one to $7E:3973 (17- or 50-province set),
# then 7 per-scenario tables (MVN, $C1:FD08 picks the record), then sets $2001 = year - 1 and $45B0.
SCENARIO_COUNT = 4
SCENARIO_MENU = 0x7BA5A                 # "1:列強争覇の章 (1560年)" x 4, NUL-terminated
WRAM_BASE, WRAM_END = 0x2000, 0x3D2B    # the scenario image in WRAM bank $7E
# (mode, year, daimyo count, block at $2000, block at $3973)
SCENARIOS = [
    (17, 1560, 17, 0x3B546, 0x3CD08),
    (50, 1560, 50, 0x377BA, 0x38743),
    (50, 1571, 38, 0x377BA, 0x38743),
    (50, 1582, 26, 0x377BA, 0x38743),
]
BLOCK_2000, BLOCK_3973 = 0xF7D, 0x3B8    # sizes
# per-scenario tables: WRAM address -> (size, ROM of scenario 1, ROM of scenario 2, stride for scenarios 2-4)
SCENARIO_TABLES = {
    0x2F7E: (0x1A8, 0x398AF, 0x38AFC, 0x1B0),   # daimyo: 53 x 8
    0x312E: (0x032, 0x3C4C4, 0x39780, 0x032),   # 50 x 01 (unknown)
    0x3160: (0x033, 0x3C4F6, 0x39816, 0x033),   # province owner (51)
    0x3193: (0x173, 0x3C529, 0x3900C, 0x173),   # daimyo surnames: 53 x 7
    0x3306: (0x109, 0x3C69C, 0x39465, 0x109),   # daimyo given names: 53 x 5
    0x340F: (0x52E, 0x3C7A5, 0x39A5F, 0x52E),   # provinces: 51 x 26
    0x393D: (0x035, 0x3CCD3, 0x3A9E9, 0x035),   # daimyo map pattern (53)
}
YEARS = 0x38737                         # LE16 x 3: start year of scenarios 2-4 ($2001 = year - 1)
DAIMYO_COUNTS = 0x3873D                 # LE16 x 3: -> $45B0 (scenario 1: 17)
DAIMYO_SLOTS = 53                       # 0-49: daimyo of province k at the start, 50-52 明智 羽柴 柴田
DAIMYO_WRAM, DAIMYO_SIZE = 0x2F7E, 8    # age, 健康, 野心, 運, 魅力, 知力, person (face) id, 0
DAIMYO_STATS = [("Health", "健康"), ("Ambition", "野心"), ("Luck", "運"), ("Charm", "魅力"), ("IQ", "知力")]
SURNAMES_WRAM, SURNAME_SIZE = 0x3193, 7
GIVEN_WRAM, GIVEN_SIZE = 0x3306, 5
OWNERS_WRAM = 0x3160
PATTERN_WRAM = 0x393D
PROVINCES_WRAM, PROVINCE_SIZE = 0x340F, 26
# Province record: 13 LE16 in this order (the FC version's order); the last one is not on any screen.
PROVINCE_FIELDS = [("Gold", "金"), ("Debt", "借金"), ("Town", "町"), ("Rice", "兵糧"), ("Kokudaka", "石高"),
                   ("Flood", "治水"), ("Loyalty", "民忠"), ("Wealth", "民財"), ("Soldiers", "兵力"),
                   ("Soldier_Loyalty", "兵忠"), ("Training", "訓練"), ("Arms", "武装"), ("Unk24", "")]
PROVINCE_COUNT_WRAM = 0x2D9C            # 0x11 or 0x32
PROVINCE_NAMES_WRAM, PROVINCE_NAME_SIZE = 0x39A7, 9
ADJ_WRAM, ADJ_SIZE = 0x3B69, 8          # neighbours, FF-terminated, zero-padded
REGIONS_WRAM = 0x3CF9                   # region 1-7 (east to west)
MODE17_PROVINCE = 0x7B9DA               # 17 bytes: 17-mode province -> 50-mode province (battle map)
PERSON_COUNT = 68                       # person ids used by the daimyo records (face = PORTRAIT_FIRST + id)

# ---------------------------------------------------------------- faces
# 40x48 = 5x6 4bpp tiles row-major (960 bytes), LZ streams 120-192: 0-67 the persons, 68-72 women (姫).
# Shown as 30 sprites with OBJ palette 5 = FACE_PALETTE.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_FIRST, PORTRAIT_COUNT = 120, 73
FACE_PALETTE = 0x7F796
EVENT_PICTURES = (44, 120)              # LZ streams 44-119: 960-byte event pictures (not decoded)

# ---------------------------------------------------------------- maps
# Strategy maps: a 30 x 20 tile bitmap (LZ stream 4 for 50 provinces, 5 for 17), tiles 0x30.. of BG2 laid out
# row by row at screen tile (1, 1), BG palette 2. Land starts as colour 0; the game paints every province
# ($C3:61AA, service 0x32 = flood fill $C0:ADE1) from a seed point with the 8 x 8 pattern of its owner
# (PATTERNS + 32 x $393D[owner]; PATTERNS + 32 x 81 if $2CFA[province] = FF).
MAP_W, MAP_H = 30, 20
MAP_STREAM = {50: 4, 17: 5}
MAP_SEED_X = {50: 0xC3D376 & 0x3FFFFF, 17: 0xC3D3DA & 0x3FFFFF}   # LE16 per province, minus 8
MAP_SEED_Y = {50: 0xC3D3FC & 0x3FFFFF, 17: 0xC3D460 & 0x3FFFFF}
PATTERNS = 0x3D508                      # 32 bytes per pattern: 8 rows x 4 bitplane bytes
UNOWNED_PATTERN = 81
MAP_PALETTE = 0x7F7F6
MAP_TILE0, MAP_SCREEN_X, MAP_SCREEN_Y = 0x30, 1, 1

# ---------------------------------------------------------------- battle maps
# 50 maps (one per 50-mode province; the 17-mode uses MODE17_PROVINCE), 11 columns x 5 rows of terrain bytes,
# row-major, the same table as the FC version. Each cell is 2 x 4 tiles (16 x 32 px), odd columns 2 tiles
# lower; the cell of terrain t uses the 8 tiles BATTLE_TILE0 + 8 k (k = BLOCK_ORDER.index(t)) row by row.
BATTLE_MAPS, BATTLE_COUNT, BATTLE_W, BATTLE_H = 0x3AA88, 50, 11, 5
BATTLE_STREAM = 0                       # 140 4bpp tiles -> BG tile 0x20
BATTLE_TILE0 = 0x20
BLANK_TILE = 0xAA
BLOCK_ORDER = [0x20, 0x10, 0x08, 0x80, 0x04, 0x40]
TERRAIN = {0x02: ("none", "場外"), 0x04: ("plain", "平地"), 0x08: ("town", "町"), 0x10: ("forest", "林"),
           0x20: ("castle", "城"), 0x40: ("water", "川・海"), 0x80: ("mountain", "山")}
BATTLE_PALETTE = 0x7F656                # BG palette 2 (palette 1 = 0x7F636, guessed to mark deployment)
BATTLE_SCREEN_X, BATTLE_SCREEN_Y = 8, 4  # BG2 tile of cell (0, 0)


def hirom(addr: int) -> int:
    return addr & 0x3FFFFF


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


def load_charset(path: str = CHARSET) -> str:
    with open(path, encoding="utf-8") as f:
        cs = "".join(line.rstrip("\n") for line in f if not line.startswith("#"))
    assert len(cs) == GLYPH_COUNT, len(cs)
    return cs


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


def flood_fill(bitmap: bytearray, width: int, height: int, x: int, y: int, pattern: bytes) -> int:
    """Paint the 4-connected colour-0 area of a tile bitmap (width x height 4bpp tiles, row-major) that contains
    pixel (x, y) with an 8-row pattern (4 bitplane bytes per row, repeated every 8 pixels). Returns the pixel
    count (0 if the seed is not colour 0)."""
    def addr(px: int, py: int) -> tuple[int, int]:
        return ((py >> 3) * width + (px >> 3)) * 32 + (py & 7) * 2, 7 - (px & 7)

    def colour(px: int, py: int) -> int:
        o, b = addr(px, py)
        return (bitmap[o] >> b & 1) | (bitmap[o + 1] >> b & 1) << 1 | (bitmap[o + 16] >> b & 1) << 2 \
            | (bitmap[o + 17] >> b & 1) << 3

    w, h = width * 8, height * 8
    if not (0 <= x < w and 0 <= y < h):
        return 0
    target = colour(x, y)
    seen = {(x, y)}
    stack = [(x, y)]
    while stack:
        px, py = stack.pop()
        for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and colour(nx, ny) == target:
                seen.add((nx, ny))
                stack.append((nx, ny))
    for px, py in seen:
        o, b = addr(px, py)
        row = pattern[4 * (py & 7):4 * (py & 7) + 4]
        for k, off in enumerate((0, 1, 16, 17)):
            bitmap[o + off] = bitmap[o + off] & ~(1 << b) | (row[k] >> b & 1) << b
    return len(seen)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        assert koei_lz.find_tables(self.data) == LZ_TABLES
        self.charset = load_charset()
        self._cache: dict[int, bytes] = {}

    # ------------------------------------------------------------ generic
    def u16(self, o: int) -> int:
        return le16(self.data, o)

    def stream_offset(self, i: int) -> int:
        return hirom(int.from_bytes(self.data[LZ_POINTERS + 3 * i:LZ_POINTERS + 3 * i + 3], "little"))

    def entry(self, i: int) -> bytes:
        """Decompressed LZ stream i (0-192)."""
        if i not in self._cache:
            self._cache[i] = koei_lz.decompress(self.data, self.stream_offset(i), LZ_TABLES)[0]
        return self._cache[i]

    def palette(self, o: int) -> list[tuple[int, int, int]]:
        return [bgr555_rgb(self.u16(o + 2 * i)) for i in range(16)]

    # ------------------------------------------------------------ text
    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g."""
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    def codes(self, raw: bytes) -> list[int]:
        """Text bytes up to 00 -> codes (two-byte glyph codes with the 00 escape undone, single bytes)."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            if raw[i] >= 0x81 and raw[i] < 0xA0 and i + 1 < len(raw):
                c = raw[i] << 8 | raw[i + 1]
                if ZERO_ESCAPE <= c < ZERO_ESCAPE + 4:
                    c = 0x8200 + (c - ZERO_ESCAPE) * 0x100
                out.append(c)
                i += 2
            else:
                out.append(raw[i])
                i += 1
        return out

    def text(self, raw: bytes) -> str:
        cs = self.codes(raw)
        out, i = [], 0
        while i < len(cs):
            for seq, s in LIGATURES.items():
                if tuple(cs[i:i + len(seq)]) == seq:
                    out.append(s)
                    i += len(seq)
                    break
            else:
                c = cs[i]
                i += 1
                if c >= CODE_BASE:
                    g = c - CODE_BASE
                    out.append(self.charset[g] if g < GLYPH_COUNT else f"[{c:04X}]")
                else:  # half-width: ASCII, JIS X 0201 kana (the screen shows hiragana)
                    ch = unicodedata.normalize("NFKC", bytes([c]).decode("cp932", errors="replace"))
                    out.append("".join(chr(ord(k) - 0x60) if "ァ" <= k <= "ン" else k for k in ch))
        return "".join(out)

    # ------------------------------------------------------------ scenarios
    def scenario_titles(self) -> list[str]:
        out, o = [], SCENARIO_MENU
        for _ in range(SCENARIO_COUNT):
            end = self.data.index(b"\0", o)
            out.append(self.text(self.data[o:end]).split(":", 1)[1])
            o = end + 1
        return out

    def scenario_sources(self, s: int) -> list[tuple[int, int, int]]:
        """[(WRAM address, ROM offset, size)] of what the loader copies for scenario s (0-3), in its order."""
        _, _, _, b2000, b3973 = SCENARIOS[s]
        out = [(WRAM_BASE, b2000, BLOCK_2000), (0x3973, b3973, BLOCK_3973)]
        for addr, (size, rom1, rom2, stride) in SCENARIO_TABLES.items():
            out.append((addr, rom1 if s == 0 else rom2 + stride * (s - 1), size))
        return out

    def scenario_image(self, s: int) -> bytes:
        """WRAM $7E:2000-$3D2A right after the loader ran (before the game adds anything)."""
        img = bytearray(WRAM_END - WRAM_BASE)
        for addr, o, size in self.scenario_sources(s):
            img[addr - WRAM_BASE:addr - WRAM_BASE + size] = self.data[o:o + size]
        year = SCENARIOS[s][1]
        img[1:3] = (year - 1).to_bytes(2, "little")
        return bytes(img)

    def scenario_year(self, s: int) -> int:
        return SCENARIOS[s][1] if s == 0 else self.u16(YEARS + 2 * (s - 1))

    def scenario_daimyo_count(self, s: int) -> int:
        return SCENARIOS[s][2] if s == 0 else self.u16(DAIMYO_COUNTS + 2 * (s - 1))

    @staticmethod
    def wram(img: bytes, addr: int, size: int) -> bytes:
        return img[addr - WRAM_BASE:addr - WRAM_BASE + size]

    def province_count(self, s: int) -> int:
        return SCENARIOS[s][0]

    def province_names(self, s: int) -> list[str]:
        img = self.scenario_image(s)
        return [self.text(self.wram(img, PROVINCE_NAMES_WRAM + PROVINCE_NAME_SIZE * p, PROVINCE_NAME_SIZE))
                for p in range(self.province_count(s))]

    def neighbours(self, s: int) -> list[list[int]]:
        img = self.scenario_image(s)
        out = []
        for p in range(self.province_count(s)):
            raw = self.wram(img, ADJ_WRAM + ADJ_SIZE * p, ADJ_SIZE)
            out.append(list(raw[:raw.index(0xFF)]))
        return out

    def daimyos(self, s: int) -> list[dict]:
        """The 53 daimyo slots of scenario s; empty slots (all zero) are left out."""
        img = self.scenario_image(s)
        owners = self.wram(img, OWNERS_WRAM, 51)
        out = []
        for d in range(DAIMYO_SLOTS):
            rec = self.wram(img, DAIMYO_WRAM + DAIMYO_SIZE * d, DAIMYO_SIZE)
            surname = self.text(self.wram(img, SURNAMES_WRAM + SURNAME_SIZE * d, SURNAME_SIZE))
            if not any(rec) and not surname:
                continue
            given = self.text(self.wram(img, GIVEN_WRAM + GIVEN_SIZE * d, GIVEN_SIZE))
            out.append({
                "index": d, "surname": surname, "given": given, "name": surname + given, "age": rec[0],
                **{k: rec[1 + i] for i, (k, _) in enumerate(DAIMYO_STATS)},
                "person": rec[6], "byte7": rec[7], "pattern": img[PATTERN_WRAM - WRAM_BASE + d],
                "provinces": [p for p in range(self.province_count(s)) if owners[p] == d],
            })
        return out

    def provinces(self, s: int) -> list[dict]:
        img = self.scenario_image(s)
        names = self.province_names(s)
        nbr = self.neighbours(s)
        out = []
        for p in range(self.province_count(s)):
            rec = self.wram(img, PROVINCES_WRAM + PROVINCE_SIZE * p, PROVINCE_SIZE)
            out.append({
                "index": p, "name": names[p], "owner": img[OWNERS_WRAM - WRAM_BASE + p],
                "region": img[REGIONS_WRAM - WRAM_BASE + p], "neighbours": nbr[p],
                "unk312E": img[0x312E - WRAM_BASE + p],
                **{k: le16(rec, 2 * i) for i, (k, _) in enumerate(PROVINCE_FIELDS)},
            })
        return out

    def mode17_province(self) -> list[int]:
        return list(self.data[MODE17_PROVINCE:MODE17_PROVINCE + 17])

    def persons(self) -> list[dict]:
        """Every person id with the name and the scenarios (1-4) that use it, in id order."""
        seen: dict[int, dict] = {}
        for s in range(SCENARIO_COUNT):
            for d in self.daimyos(s):
                p = seen.setdefault(d["person"], {"id": d["person"], "name": d["name"], "surname": d["surname"],
                                                  "given": d["given"], "scenarios": []})
                assert p["name"] == d["name"], (p, d)
                p["scenarios"].append(s + 1)
        return [seen[k] for k in sorted(seen)]

    # ------------------------------------------------------------ faces
    def face_raw(self, n: int) -> bytes:
        """960 bytes (30 4bpp tiles) of portrait n (0-72)."""
        raw = self.entry(PORTRAIT_FIRST + n)
        assert len(raw) == FACE_BYTES
        return raw

    def face_pixels(self, n: int) -> bytes:
        """Portrait n -> 40x48 colour numbers 0-15."""
        raw = self.face_raw(n)
        px = bytearray(40 * 48)
        for t in range(FACE_W * FACE_H):
            cx, cy = t % FACE_W * 8, t // FACE_W * 8
            for i, v in enumerate(decode_tile(raw[32 * t:32 * t + 32])):
                px[(cy + i // 8) * 40 + cx + i % 8] = v
        return bytes(px)

    def face_palette(self) -> list[tuple[int, int, int]]:
        return self.palette(FACE_PALETTE)

    def face_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = self.face_palette()
        return [pal[v] for v in self.face_pixels(n)]

    # ------------------------------------------------------------ maps
    def map_seeds(self, mode: int) -> list[tuple[int, int]]:
        return [(self.u16(MAP_SEED_X[mode] + 2 * p) - 8, self.u16(MAP_SEED_Y[mode] + 2 * p) - 8) for p in range(mode)]

    def pattern(self, k: int) -> bytes:
        return self.data[PATTERNS + 32 * k:PATTERNS + 32 * k + 32]

    def map_bitmap(self, s: int | None = None, mode: int = 50) -> bytes:
        """The map's 600 tiles (4bpp) as the game shows them at the start of scenario s (provinces painted with
        their owners' patterns), or unpainted if s is None."""
        if s is not None:
            mode = self.province_count(s)
        bm = bytearray(self.entry(MAP_STREAM[mode]))
        if s is not None:
            img = self.scenario_image(s)
            for p, (x, y) in enumerate(self.map_seeds(mode)):
                if img[0x2CFA - WRAM_BASE + p] == 0xFF:
                    pat = self.pattern(UNOWNED_PATTERN)
                else:
                    pat = self.pattern(img[PATTERN_WRAM - WRAM_BASE + img[OWNERS_WRAM - WRAM_BASE + p]])
                flood_fill(bm, MAP_W, MAP_H, x, y, pat)
        return bytes(bm)

    def map_rgb(self, s: int | None = None, mode: int = 50) -> tuple[int, int, list]:
        bm = self.map_bitmap(s, mode)
        pal = self.palette(MAP_PALETTE)
        w, h = MAP_W * 8, MAP_H * 8
        px = [(0, 0, 0)] * (w * h)
        for t in range(MAP_W * MAP_H):
            cx, cy = t % MAP_W * 8, t // MAP_W * 8
            for i, v in enumerate(decode_tile(bm[32 * t:32 * t + 32])):
                px[(cy + i // 8) * w + cx + i % 8] = pal[v]
        return w, h, px

    # ------------------------------------------------------------ battle maps
    def battle_cells(self, m: int) -> bytes:
        o = BATTLE_MAPS + m * BATTLE_W * BATTLE_H
        return self.data[o:o + BATTLE_W * BATTLE_H]

    def battle_tilemap(self, m: int, cells: bytes | None = None) -> list[int]:
        """Tile ids of map m as BG2 shows them: 22 x 22 tiles (11 columns of 2 tiles, 5 rows of 4 tiles plus the
        2-tile offset of odd columns), BLANK_TILE outside the cells."""
        cells = self.battle_cells(m) if cells is None else cells
        tw, th = 2 * BATTLE_W, 4 * BATTLE_H + 2
        ids = [BLANK_TILE] * (tw * th)
        for r in range(BATTLE_H):
            for c in range(BATTLE_W):
                v = cells[r * BATTLE_W + c]
                if v not in BLOCK_ORDER:
                    continue
                t0 = BATTLE_TILE0 + 8 * BLOCK_ORDER.index(v)
                y0 = 4 * r + 2 * (c & 1)
                for j in range(4):
                    for i in range(2):
                        ids[(y0 + j) * tw + 2 * c + i] = t0 + 2 * j + i
        return ids

    def battle_rgb(self, m: int) -> tuple[int, int, list]:
        """Map m as an image (the cells with BG palette 2; outside the cells, where the game shows BLANK_TILE with
        palette 7, black)."""
        ids = self.battle_tilemap(m)
        chars = self.entry(BATTLE_STREAM)
        pal = self.palette(BATTLE_PALETTE)
        tw, th = 2 * BATTLE_W, 4 * BATTLE_H + 2
        px = [(0, 0, 0)] * (tw * 8 * th * 8)
        for n, t in enumerate(ids):
            if t == BLANK_TILE:
                continue
            k = t - BATTLE_TILE0
            pix = decode_tile(chars[32 * k:32 * k + 32])
            cx, cy = n % tw * 8, n // tw * 8
            for i, v in enumerate(pix):
                px[(cy + i // 8) * tw * 8 + cx + i % 8] = pal[v]
        return tw * 8, th * 8, px
