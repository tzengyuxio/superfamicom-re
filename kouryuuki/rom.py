"""SFC 項劉記 (KOEI, 1996) ROM decoding.

Offsets are file offsets of the headerless 1.5 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Kouryuuki (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

# Compressed data: 727 long pointers to streams for the decompressor at $C0:A2AB (same algorithm and tables
# as 天翔記's $C0:F194; entry 0 is not a stream)
DATA_TABLE = 0x9E0E5
DATA_COUNT = 727
LEN_VALUE, LEN_BITS, LEN_SHIFT = 0xA14E, 0xA18E, 0xA1CD
NEAR_OFFSET, NEAR_BITS = 0xA1D5, 0xA295
FAR_SHIFT, FAR_BITS = 0xA29E, 0xA2A3

# Font: 16x16 1bpp glyphs of 32 bytes (four 8x8 tiles: top-left, top-right, bottom-left, bottom-right, one byte
# per row). Glyphs 0-1023 at FONT_LOW, 1024-1287 at FONT_HIGH. Text code 0x8140 + g is glyph g.
FONT_LOW = 0x0000
FONT_HIGH = 0x17DF00
GLYPH_COUNT = 1288
TEXT_BASE = 0x8140

SCENARIO_COUNT = 4
SCENARIO_YEARS = [206, 205, 204, 203]   # BC
SCENARIO_MENU = 0x9DFCD                 # "1 前206年 漢中王即位す" ... (text, one line per scenario)

# Persons 0-91: 17 bytes = name (3 text codes, 0-padded), 0, reading (8 half-width katakana, 0-padded),
# age in 206 BC (born = 206 + age BC), 1 unknown byte
PERSON_NAMES = 0x1668A
PERSON_COUNT = 92
PERSON_NAME_SIZE = 17
# Places 0-38: 19 bytes = name (3 codes), 0, reading (7), 3 unknown bytes, map cell LE16 (MAP_W wide)
PLACE_NAMES = 0x16CA6
PLACE_COUNT = 39
PLACE_NAME_SIZE = 19
BIO_TABLE = 0x9D939                     # 2 long pointers: 項羽's and 劉邦's profile text

# Scenario state: WRAM $7E:2000-$7E:472C, copied from ROM pieces (wram address, file offset, length)
SCENARIO_WRAM, SCENARIO_SIZE = 0x2000, 0x272D
SCENARIO_PIECES = [
    [(0x2000, 0x16F8B, 0x12F8), (0x32F8, 0x4D6E3, 0x398), (0x3690, 0x18283, 0x57C), (0x3C0C, 0x7D5AC, 0xA71),
     (0x467D, 0x187FF, 0xB0)],
    [(0x2000, 0x3D172, 0x12F8), (0x32F8, 0x6E1EC, 0x398), (0x3690, 0x188AF, 0x109D)],
    [(0x2000, 0x1994C, 0x272D)],
    [(0x2000, 0x1C079, 0x272D)],
]
PERSONS_AT, PERSON_SIZE = 0x32F8, 10    # 92 records
PLACES_AT, PLACE_SIZE = 0x3690, 36      # 39 records
ARMIES_AT, ARMY_SIZE, ARMY_COUNT = 0x3C0C, 27, 99
FACTION_COUNT = 16
DIPLOMACY = "DCBA"                      # person +1 // 2

# Faces: 40x48 = 5x6 4bpp tiles, row-major; person n's face is data entry FACE_ENTRY + n ($C9:4341), shown
# with the one palette FACE_PALETTE (sprite palette 0, $C2:28E0)
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
FACE_ENTRY = 21
FACE_COUNT = 97
FACE_PALETTE = 0x9E9EA

# Big map: 55 x 44 cells; each cell is drawn as 4 x 4 BG tiles by $C2:0E8C (not decoded yet)
MAP_W, MAP_H = 55, 44
MAP_ROADS = 1                           # data entry: 0 = road cell, 1 = other
MAP_FEATURES = 2                        # data entry: per-cell feature number (0-48)


def hirom(addr: int) -> int:
    return addr & 0x3FFFFF


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


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


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


def decompress(rom: bytes, p: int, limit: int = 1 << 20) -> tuple[bytes, int]:
    """The game's decompressor ($C0:A2AB): (output, end offset of the stream).

    A 16-bit bit window W is filled from little-endian words of the stream; flag bytes and literals
    are read from the same pointer in between. Flag bits (MSB first): 1 = literal byte; 0 = copy
    length + 1 bytes from distance + 1 back, with a prefix-coded length and distance taken from W.
    The length value 0xFF ends the stream.
    """
    w = n = avail = 0

    def take(bits: int) -> None:  # shift `bits` new bits into W
        nonlocal w, n, avail, p
        w = (w << bits) & 0xFFFF
        if avail >= bits:
            avail -= bits
            w |= (n >> avail) & ((1 << bits) - 1)
        else:
            need = bits - avail
            w |= ((n & ((1 << avail) - 1)) << need) & 0xFFFF
            n = rom[p] | rom[p + 1] << 8
            p += 2
            avail = 16 - need
            w |= (n >> avail) & ((1 << need) - 1)

    take(16)
    out = bytearray()
    while len(out) < limit:
        flags = rom[p]
        p += 1
        for k in range(8):
            if flags >> (7 - k) & 1:
                out.append(rom[p])
                p += 1
                continue
            if w & 0x8000:
                length = 1
            else:
                y = w >> 9
                if y == 0:
                    length = (w >> 2) | 0x80
                    if length == 0xFF:
                        return bytes(out), p
                elif y < 8:
                    length = (w >> 1) >> (rom[LEN_SHIFT + y] // 2)
                else:
                    length = rom[LEN_VALUE + y]
                take(rom[LEN_BITS + y] // 2)
            if (w << 1) & 0xFFFF < 0x6000:
                y = ((w << 2) & 0xFFFF) >> 8
                dist, bits = rom[NEAR_OFFSET + y], rom[NEAR_BITS + (y >> 4)] // 2
            else:
                y = (w >> 12) & 7
                dist, bits = ((w & 0x0FFF) | 0x1000) >> (rom[FAR_SHIFT + y] // 2), rom[FAR_BITS + y] // 2
            take(bits)
            s = len(out) - dist - 1
            for j in range(length + 1):
                out.append(out[s + j])
    return bytes(out), p


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.charset = load_charset()
        self._cache: dict[int, bytes] = {}

    def entry(self, i: int) -> bytes:
        """Decompressed data entry i of DATA_TABLE."""
        if i not in self._cache:
            p = hirom(int.from_bytes(self.data[DATA_TABLE + 3 * i:DATA_TABLE + 3 * i + 3], "little"))
            self._cache[i] = decompress(self.data, p)[0]
        return self._cache[i]

    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g."""
        a = FONT_LOW + 32 * g if g < 1024 else FONT_HIGH + 32 * (g - 1024)
        raw = self.data[a:a + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    def text(self, raw: bytes) -> str:
        """Game text -> str: 2-byte codes 0x8140+ through the charset, half-width katakana and ASCII as cp932,
        0A newline, 09 (indent) dropped, ESC 'C' n (colour) dropped, 00 ends."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            c = raw[i]
            if 0x81 <= c < 0xA0 or c >= 0xE0:
                out.append(self.charset[(c << 8 | raw[i + 1]) - TEXT_BASE])
                i += 2
            elif c == 0x1B:
                i += 3
            elif c == 0x09:
                i += 1
            else:
                out.append("\n" if c == 0x0A else bytes([c]).decode("cp932", "replace"))
                i += 1
        return "".join(out)

    def scenario_titles(self) -> list[str]:
        return [line.split(" ", 2)[2] for line in self.text(self.data[SCENARIO_MENU:SCENARIO_MENU + 200]).splitlines()]

    def persons(self) -> list[dict]:
        out = []
        for pid in range(PERSON_COUNT):
            o = PERSON_NAMES + PERSON_NAME_SIZE * pid
            r = self.data[o:o + PERSON_NAME_SIZE]
            out.append({"id": pid, "offset": o, "name": self.text(r[0:6]), "reading": r[7:15].rstrip(b"\0").decode("cp932"),
                        "born": SCENARIO_YEARS[0] + r[15], "unknown": r[16]})
        return out

    def places(self) -> list[dict]:
        out = []
        for i in range(PLACE_COUNT):
            o = PLACE_NAMES + PLACE_NAME_SIZE * i
            r = self.data[o:o + PLACE_NAME_SIZE]
            cell = le16(r, 17)
            out.append({"id": i, "name": self.text(r[0:6]), "reading": r[7:14].rstrip(b"\0").decode("cp932"),
                        "x": cell % MAP_W, "y": cell // MAP_W, "unknown": r[14:17].hex()})
        return out

    def bios(self) -> list[str]:
        out = []
        for i in range(2):
            p = hirom(int.from_bytes(self.data[BIO_TABLE + 3 * i:BIO_TABLE + 3 * i + 3], "little"))
            out.append(self.text(self.data[p:p + 400]))
        return out

    def scenario_image(self, sc: int) -> bytes:
        """WRAM $7E:2000-$7E:472C as the game loads scenario sc."""
        img = bytearray(SCENARIO_SIZE)
        for at, src, n in SCENARIO_PIECES[sc]:
            img[at - SCENARIO_WRAM:at - SCENARIO_WRAM + n] = self.data[src:src + n]
        return bytes(img)

    def scenario_persons(self, sc: int) -> list[dict]:
        """+0 bits 4-7 勢力, bits 0-3 flags (0 = 君主), +1 外交 (DIPLOMACY[v // 2]), +2 軍 (army slot),
        +3 体力, +4 体力上限, +5 戦闘, +6 統率, +7 用兵, +8 経験, +9 unknown."""
        img = self.scenario_image(sc)
        out = []
        for pid in range(PERSON_COUNT):
            o = PERSONS_AT - SCENARIO_WRAM + PERSON_SIZE * pid
            r = img[o:o + PERSON_SIZE]
            out.append({"id": pid, "raw": r, "faction": r[0] >> 4, "flags": r[0] & 15, "diplomacy": r[1], "army": r[2],
                        "hp": r[3], "hp_max": r[4], "war": r[5], "command": r[6], "tactics": r[7], "exp": r[8],
                        "unknown": r[9]})
        return out

    def scenario_places(self, sc: int) -> list[dict]:
        """+0 金, +2 ?, +4 食料, +6 ?, +8 人口, +10 人口上限? (LE16), +12 勢力 (FF = none),
        +13 + f 支持 of 勢力 f (16), +29 疲弊, +30 防御, +31 農地, +32..35 unknown."""
        img = self.scenario_image(sc)
        out = []
        for i in range(PLACE_COUNT):
            o = PLACES_AT - SCENARIO_WRAM + PLACE_SIZE * i
            r = img[o:o + PLACE_SIZE]
            out.append({"id": i, "raw": r, "gold": le16(r, 0), "food": le16(r, 4), "population": le16(r, 8),
                        "population2": le16(r, 10), "unknown2": le16(r, 2), "unknown6": le16(r, 6), "faction": r[12],
                        "support": list(r[13:13 + FACTION_COUNT]), "fatigue": r[29], "defense": r[30], "farm": r[31]})
        return out

    def scenario_armies(self, sc: int) -> list[dict]:
        """+0 next army of the list (WRAM address, 0 = end), +2 資金, +4 兵糧, +6 兵士, +8 所在 (place),
        +9 unknown, +21 士気, +22 将 (person), +23 武装, +25 勢力. Slots with 将 FF are unused."""
        img = self.scenario_image(sc)
        out = []
        for i in range(ARMY_COUNT):
            o = ARMIES_AT - SCENARIO_WRAM + ARMY_SIZE * i
            r = img[o:o + ARMY_SIZE]
            out.append({"id": i, "raw": r, "next": le16(r, 0), "gold": le16(r, 2), "food": le16(r, 4),
                        "soldiers": le16(r, 6), "place": r[8], "morale": r[21], "leader": r[22], "arms": r[23],
                        "faction": r[25]})
        return out

    def face_palette(self) -> list[int]:
        return [le16(self.data, FACE_PALETTE + 2 * i) for i in range(16)]

    def face_tiles(self, n: int) -> bytes:
        return self.entry(FACE_ENTRY + n)[:FACE_BYTES]

    def face_pixels(self, n: int) -> list[int]:
        """40x48 colour numbers of face n, row-major."""
        tiles = self.face_tiles(n)
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(n)]
