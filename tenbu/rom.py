"""SFC 三国志正史 天舞スピリッツ (WOLF TEAM / TELENET JAPAN) ROM decoding.

Headerless 1.5 MB LoROM (map 0x20, SlowROM): CPU $bb:8000-$FFFF = file 0x8000 bb + (addr - 0x8000). Text is
Shift-JIS stored as byte pairs; the font holds only the codes of a kanji list (data/charset.txt for 92 custom
codes). Scenario data are LZSS streams. See docs/ROM_FORMAT.md; what is verified and what is not is listed in
README.md.
"""
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
from paths import ORIGINAL

DEFAULT_ROM = os.path.join(ORIGINAL, "Sangokushi Seishi - Tenbu Spirits (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

# LZSS ($00:A527, A = bank, Y = address, output to WMDATA $2180): LE32 compressed length, LE32 output size, then
# flag bytes (LSB first, 1 = literal; 0 = lo, hi: offset lo | (hi & 0xF0) << 4, length (hi & 15) + 3) over a
# 4096-byte ring starting at 0xFEE with a fixed prefill (lz_prefill)
LZ_DECODER = 0x00A527

# Scenarios ($00:CA31, A = scenario 0-3): 12 chained streams from $08:8000, 3 per scenario
SCENARIO_STREAMS = 0x40000
LOADER, LOADER_DONE = 0x00CA31, 0x00CA8D
SCENARIO_YEARS = [190, 200, 215, 227]
SCENARIO_TITLES_AT = 0x10D617        # 4 x 4 SJIS chars: 後漢戦国 龍虎激突 天下三分 武侯出師; 易普難 follows
PERSON_COUNT, PERSON_SIZE, PERSON_WRAM = 600, 35, 0x8018
FACTION_COUNT, FACTION_SIZE, FACTION_WRAM = 15, 30, 0xD220
PROVINCE_COUNT, PROVINCE_SIZE, PROVINCE_WRAM = 126, 32, 0xD3E2

# Person record (35 bytes). "?" = meaning guessed, not verified.
PERSON_FIELDS = [  # (name, offset, size)
    ("状態", 14, 1), ("政", 15, 1), ("外", 16, 1), ("策", 17, 1), ("采", 18, 1), ("武", 19, 1), ("徳", 20, 1),
    ("忠誠?", 21, 1), ("血縁", 22, 2), ("勢力", 24, 1), ("身分?", 25, 1), ("年齢", 26, 1), ("寿命?", 27, 1),
    ("+28", 28, 1), ("所在", 29, 1), ("登場?", 30, 1), ("顔", 31, 2), ("官職", 33, 1), ("+34", 34, 1),
]
# Faction record (30 bytes): name (6), ruler, +8 person or FFFF (漢: 122 劉協), +10 value, +12 capital 郡国?,
# +13, +14, +15-29 relations with the 15 factions (diagonal 0)
FACTION_FIELDS = [("君主", 6, 2), ("+8", 8, 2), ("+10", 10, 2), ("都城?", 12, 1), ("+13", 13, 1), ("+14", 14, 1)]
# 郡国 record (32 bytes): +0 faction (FF none), +2 / +3 = PROVINCE_POS, the fields of the 郡国 window (verify_provinces):
# 人口 = +4 x 100, 兵 LE32, 金, 糧, 士 (+22; its maximum is 80 when the high nibble of +27 is F, else 100), 規模 = low
# nibble of +27 (PROVINCE_SIZES), 太 = person +28 (FFFF none); the other fields are not identified
PROVINCE_FIELDS = [("勢力", 0, 1), ("+1", 1, 1), ("X", 2, 1), ("Y", 3, 1), ("人口/100", 4, 2), ("兵", 6, 4), ("金", 10, 2),
                   ("糧", 12, 2), ("+14", 14, 2), ("+16", 16, 2), ("+18", 18, 1), ("士", 22, 1), ("+23", 23, 1),
                   ("+24", 24, 1), ("+25", 25, 1), ("+26", 26, 1), ("+27", 27, 1), ("太", 28, 2)]
PROVINCE_SIZES = 0x32943              # $06:A943: 規模 names 無 小 中 大 巨 (SJIS + FFFF)

# Name tables (uncompressed SJIS, FFFF-terminated)
PROVINCE_POS = 0x318FF               # 126 x (x, y) in 16-pixel units of the local map
PROVINCE_NAMES = 0x319FD             # 126 x (6 bytes + FFFF)
PROVINCE_READINGS = 0x31DEF          # 126 x 8 half-width (JIS X 0201) bytes
OFFICES, OFFICE_COUNT = 0x321DF, 48  # 26 bytes: name 10 + FFFF + modern name 10 + FFFF + 2 bytes ($00:C9E3)
STATES, STATE_COUNT = 0x326BF, 13    # 州: 4 bytes + FFFF
PEOPLES, PEOPLE_COUNT = 0x3270D, 15  # 異民族: 6 bytes + FFFF
KINGDOMS, KINGDOM_COUNT = 0x327C5, 41  # 王号: 6 bytes + FFFF

# Font: the kanji list ($00:BE6B) maps an SJIS code to glyph 0x6B + index (not found: 0x23); codes below 0x48 are
# glyph numbers (4bpp button labels). Glyph g = tiles 4g..4g+3 (TL TR BL BR). Tile t < 0x120: 4bpp at
# FONT + 32 t; t >= 0x120: 1bpp at FONT + 0x2400 + 8 (t - 0x120) ($00:A086 / $00:A47B)
KANJI_LIST, KANJI_COUNT = 0x30180, 1113
GLYPH_BASE = 0x6B
FONT = 0x160000
HALF_ORDER = "0123456789ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜｦﾝﾟﾞｬｭｮｯｧｨｩｪｫ/ｰ "  # half-width h: tiles
# 0x120 + 2h (top) and 0x121 + 2h (bottom)
BUTTONS = "人令兵可否外将年徳采政交軍栄武治"  # glyphs 0x00-0x0F as read by eye (0x10-0x1F not all identified)

# Portraits: 250 x 4bpp 32 x 40 (4 x 5 tiles, row-major), one 16-colour palette ($21:CE4C, index = person +31)
FACES, FACE_COUNT, FACE_W, FACE_H = 0x134800, 250, 32, 40
FACE_PALETTE = 0x2FFA9

# Local map ($00:BCEE): 270 x 230 chip numbers, chip v = 4bpp 8 x 8 tile at MAP_CHIPS + 32 v, palette MAP_PALETTE
MAP, MAP_W, MAP_H = 0x170000, 270, 230
MAP_CHIPS, MAP_PALETTE = 0x130000, 0x24688
# Cell table ($00:BC19): 135 x 115 cells of 16 px; 0x81 + id = city of 郡国 id, other values terrain classes
CELLS, CELLS_W, CELLS_H = 0x38200, 135, 115
# 中国全土図 (ruler selection): stream at $24:94CD, 868 4bpp tiles = 31 x 28 tiles row-major, palette below
REGION_STREAM, REGION_W, REGION_H, REGION_PALETTE = 0x1214CD, 31, 28, 0x124859


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


def load_charset(path: str = CHARSET) -> dict[bytes, str]:
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            code, ch = line.rstrip("\n").split("\t")
            out[bytes.fromhex(code)] = ch
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return tuple((c >> s & 31) << 3 | (c >> s & 31) >> 2 for s in (0, 5, 10))


def palette(raw: bytes) -> list[tuple[int, int, int]]:
    return [bgr555_rgb(le16(raw, 2 * i)) for i in range(len(raw) // 2)]


def lz_prefill() -> bytearray:
    b = bytearray()
    for v in range(256):
        b += bytes([v]) * 13
    b += bytes(range(256)) + bytes(range(255, -1, -1)) + bytes(128) + b" " * 0x6E
    return b + bytes(4096 - len(b))


def lz(data: bytes, o: int) -> tuple[bytes, int]:
    """Decompress the stream at file offset o; returns (output, offset of the next chained stream)."""
    n, size = struct.unpack_from("<II", data, o)
    ring, r, out, i = lz_prefill(), 0xFEE, bytearray(), o + 8
    while len(out) < size:
        flags = data[i]
        i += 1
        for b in range(8):
            if len(out) >= size:
                break
            if flags >> b & 1:
                c = data[i]
                i += 1
                out.append(c)
                ring[r] = c
                r = (r + 1) & 0xFFF
            else:
                lo, hi = data[i], data[i + 1]
                i += 2
                p = lo | (hi & 0xF0) << 4
                for k in range((hi & 15) + 3):
                    c = ring[(p + k) & 0xFFF]
                    out.append(c)
                    ring[r] = c
                    r = (r + 1) & 0xFFF
    return bytes(out[:size]), o + 8 + n


def decode_tile4(raw: bytes) -> list[int]:
    out = []
    for y in range(8):
        for x in range(8):
            out.append(sum((raw[(p // 2) * 16 + 2 * y + (p & 1)] >> (7 - x) & 1) << p for p in range(4)))
    return out


def decode_fields(raw: bytes, fields) -> dict:
    return {name: int.from_bytes(raw[o:o + n], "little") for name, o, n in fields}


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.charset = load_charset()
        self._scen = {}
        self._kanji = None

    # --- text
    def sjis(self, raw: bytes) -> str:
        out = []
        for i in range(0, len(raw) - 1, 2):
            pair = raw[i:i + 2]
            if pair == b"\xff\xff":
                break
            out.append(self.charset.get(pair) or pair.decode("cp932", errors="replace"))
        return "".join(out)

    def half(self, raw: bytes) -> str:
        return raw.decode("cp932", errors="replace").strip()

    def glyph_of(self, pair: bytes) -> int:
        """Glyph number of one SJIS code as $00:BE6B finds it (values below 0x48 are glyph numbers)."""
        v = pair[0] | pair[1] << 8
        if v < 0x48:
            return v
        if self._kanji is None:
            self._kanji = {c: i for i, c in reversed(list(enumerate(self.kanji_list())))}
        i = self._kanji.get(pair)
        return GLYPH_BASE + i if i is not None else 0x23

    def text_codes(self, raw: bytes) -> list[int]:
        """Tile codes $00:A0CA gets for SJIS text: 0x8000 | 4 g + 0..3 per character."""
        return [0x8000 | 4 * self.glyph_of(raw[i:i + 2]) + k for i in range(0, len(raw), 2) for k in range(4)]

    @staticmethod
    def half_codes(raw: bytes) -> list[int]:
        """Tile codes of half-width text: 0x8120 + 2 h, 0x8121 + 2 h (h = position in HALF_ORDER)."""
        out = []
        for b in raw:
            h = HALF_ORDER.index(bytes([b]).decode("cp932"))
            out += [0x8120 + 2 * h, 0x8121 + 2 * h]
        return out

    def kanji_list(self) -> list[bytes]:
        return [self.data[KANJI_LIST + 2 * i:KANJI_LIST + 2 * i + 2] for i in range(KANJI_COUNT)]

    def glyph(self, g: int) -> list[int]:
        """16 x 16 glyph g as 256 values (1bpp: 0 / 1; 4bpp button glyphs: colour 0-15)."""
        px = [0] * 256
        for k, (dx, dy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
            t = 4 * g + k
            if t < 0x120:
                tile = decode_tile4(self.data[FONT + 32 * t:FONT + 32 * t + 32])
            else:
                b = self.data[FONT + 0x2400 + 8 * (t - 0x120):][:8]
                tile = [b[y] >> (7 - x) & 1 for y in range(8) for x in range(8)]
            for y in range(8):
                for x in range(8):
                    px[(dy + y) * 16 + dx + x] = tile[y * 8 + x]
        return px

    # --- scenarios
    def scenario_streams(self, k: int) -> list[int]:
        o = SCENARIO_STREAMS
        offs = []
        for _ in range(3 * (k + 1)):
            offs.append(o)
            o = lz(self.data, o)[1]
        return offs[-3:]

    def scenario_wram(self, k: int) -> dict[int, bytes]:
        """WRAM blocks written by the loader $00:CA31 for scenario k."""
        if k not in self._scen:
            a, b, c = (lz(self.data, o)[0] for o in self.scenario_streams(k))
            self._scen[k] = {PERSON_WRAM: a, FACTION_WRAM: b, PROVINCE_WRAM: c}
        return self._scen[k]

    def person_raw(self, k: int, p: int) -> bytes:
        return self.scenario_wram(k)[PERSON_WRAM][PERSON_SIZE * p:PERSON_SIZE * (p + 1)]

    def person(self, k: int, p: int) -> dict:
        raw = self.person_raw(k, p)
        return {"名前": self.sjis(raw[:6]), "読み": self.half(raw[6:14]), **decode_fields(raw, PERSON_FIELDS)}

    def faction_raw(self, k: int, f: int) -> bytes:
        return self.scenario_wram(k)[FACTION_WRAM][FACTION_SIZE * f:FACTION_SIZE * (f + 1)]

    def faction(self, k: int, f: int) -> dict | None:
        raw = self.faction_raw(k, f)
        if raw[6:8] == b"\xff\xff":
            return None
        return {"名前": self.sjis(raw[:6]), **decode_fields(raw, FACTION_FIELDS), "関係": list(raw[15:30])}

    def province_raw(self, k: int, c: int) -> bytes:
        return self.scenario_wram(k)[PROVINCE_WRAM][PROVINCE_SIZE * c:PROVINCE_SIZE * (c + 1)]

    def province(self, k: int, c: int) -> dict:
        v = decode_fields(self.province_raw(k, c), PROVINCE_FIELDS)
        v["規模"] = self.sjis(self.data[PROVINCE_SIZES + 4 * (v["+27"] & 15):][:2])
        v["士上限"] = 80 if v["+27"] >> 4 == 15 else 100
        return v

    def scenario_titles(self) -> list[str]:
        s = self.data[SCENARIO_TITLES_AT:SCENARIO_TITLES_AT + 32].decode("cp932")
        return [s[4 * i:4 * i + 4] for i in range(4)]

    # --- name tables
    def province_name(self, c: int) -> str:
        return self.sjis(self.data[PROVINCE_NAMES + 8 * c:][:6])

    def province_reading(self, c: int) -> str:
        return self.half(self.data[PROVINCE_READINGS + 8 * c:][:8])

    def province_pos(self, c: int) -> tuple[int, int]:
        return self.data[PROVINCE_POS + 2 * c], self.data[PROVINCE_POS + 2 * c + 1]

    def office(self, n: int) -> tuple[str, str, bytes]:
        """(name, modern name shown when $0CA7 is set, the 2 bytes after the entry)."""
        o = OFFICES + 26 * n
        return self.sjis(self.data[o:o + 10]), self.sjis(self.data[o + 12:o + 22]), self.data[o + 24:o + 26]

    def table_names(self, base: int, count: int, size: int) -> list[str]:
        return [self.sjis(self.data[base + (size + 2) * i:][:size]) for i in range(count)]

    def states(self) -> list[str]:
        return self.table_names(STATES, STATE_COUNT, 4)

    def peoples(self) -> list[str]:
        return self.table_names(PEOPLES, PEOPLE_COUNT, 6)

    def kingdoms(self) -> list[str]:
        return self.table_names(KINGDOMS, KINGDOM_COUNT, 6)

    # --- graphics
    def face_rgb(self, n: int) -> list[tuple[int, int, int] | None]:
        """Face n as FACE_W x FACE_H pixels (None = colour 0, transparent)."""
        pal = palette(self.data[FACE_PALETTE:FACE_PALETTE + 32])
        raw = self.data[FACES + 640 * n:FACES + 640 * (n + 1)]
        px = [None] * (FACE_W * FACE_H)
        for t in range(20):
            tile = decode_tile4(raw[32 * t:32 * t + 32])
            tx, ty = t % 4, t // 4
            for i, v in enumerate(tile):
                px[(ty * 8 + i // 8) * FACE_W + tx * 8 + i % 8] = pal[v] if v else None
        return px

    def chip_image(self, base: int, tiles: list[int], w: int, pal_at: int) -> tuple[list[int], list]:
        """Indexed pixels of a w-tile-wide grid of 4bpp tiles (tile numbers relative to base) + palette."""
        h = len(tiles) // w
        px = [0] * (w * 8 * h * 8)
        cache = {}
        for i, t in enumerate(tiles):
            if t not in cache:
                cache[t] = decode_tile4(self.data[base + 32 * t:base + 32 * t + 32])
            tx, ty = i % w, i // w
            for j, v in enumerate(cache[t]):
                px[(ty * 8 + j // 8) * w * 8 + tx * 8 + j % 8] = v
        return px, palette(self.data[pal_at:pal_at + 32])

    def local_map(self) -> tuple[list[int], list]:
        return self.chip_image(MAP_CHIPS, list(self.data[MAP:MAP + MAP_W * MAP_H]), MAP_W, MAP_PALETTE)

    def cells(self) -> bytes:
        return self.data[CELLS:CELLS + CELLS_W * CELLS_H]

    def region_map(self) -> tuple[list[int], list]:
        tiles = lz(self.data, REGION_STREAM)[0]
        px = [0] * (REGION_W * 8 * REGION_H * 8)
        for t in range(REGION_W * REGION_H):
            tile = decode_tile4(tiles[32 * t:32 * t + 32])
            tx, ty = t % REGION_W, t // REGION_W
            for j, v in enumerate(tile):
                px[(ty * 8 + j // 8) * REGION_W * 8 + tx * 8 + j % 8] = v
        return px, palette(self.data[REGION_PALETTE:REGION_PALETTE + 32])
