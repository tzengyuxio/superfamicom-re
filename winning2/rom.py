"""SFC ウイニングポスト2 (KOEI, 1995) ROM decoding, also ウイニングポスト2 プログラム'96 (original and Rev 1).

Headerless 3 MB HiROM image (banks $C0-$EF, file offset = CPU address & 0x3FFFFF). Native 65816 code compiled from C;
graphics are KOEI LZ streams (tools/koei_lz.py). Text uses the game's own 2-byte codes 0x8140 + glyph
(data/charset.txt), 12x12 1bpp glyphs. Horse names are pairs of name-part numbers (9 katakana bytes each), people
are pairs of 6-byte name parts. The initial game state is copied from banks $E7-$EA into WRAM when a new game
starts ($C3:0F12). See winning2/docs/ROM_FORMAT.md.

Program '96 is the same program rebuilt with updated data: every table has the same record layout but sits
elsewhere (PROGRAM96), its font has one more glyph (data/charset_96.txt), it has 1162 races (930 names) and 27 more
faces (codes 208-234), and it picks the faces of some jockeys and trainers differently (face_code). Its Rev 1 uses
the same offsets (8 race records and one schedule entry differ).
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Winning Post 2 (Japan).zip")
PROGRAM96_ROM = os.path.join(REPO, "roms", "Winning Post 2 - Program '96 (Japan).zip")

# File offsets. INIT_* are the ROM sources of the new-game copies ($C3:0F12, memcpy $C1:1D60).
ORIGINAL = {
    "FONT": 0x1201D4,           # 3276 x 18: 12x12 1bpp glyphs ($D2:01D4, pointer at $C1:C7F4)
    "GLYPH_COUNT": 3276,
    "CHARSET": "charset.txt",
    "PERSON_PART": 0x2AAD39,    # 1003 x 6: name parts of people, 3 glyph codes, 0-padded ($EA:AD39)
    "PERSON_PART_COUNT": 1003,  # 1001 ユーザ, 1002 プレイ(ヤー)
    "HORSE_PART": 0x2908BB,     # 6000 x 9: horse name parts, katakana bytes ($E9:08BB)
    "RACEHORSE": 0x2A6D74,      # -> WRAM $488D, 140 x 45
    "INIT_687C": 0x2A8610,      # -> WRAM $687C, 0x123E bytes (not decoded)
    "STALLION": 0x2A984E,       # -> WRAM $886D, 255 x 21
    "MARE": 0x27E124,           # -> WRAM $7ABA, 140 x 13
    "JOCKEY": 0x28E0B8,         # -> WRAM $9D58, 60 x 18
    "TRAINER": 0x27E840,        # -> WRAM $8492, 20 x 12
    "OWNER": 0x2AC5D5,          # -> WRAM $A4D8, 29 x 15
    "INIT_A68B": 0x290744,      # -> WRAM $A68B, 25 x 5 (all zero)
    "FOAL": 0x29DE7B,           # -> WRAM $81D6, 80 x 7
    "ROM_JOCKEY": 0x290000,     # 50 x 18: jockeys 60-109 read from ROM ($C4:A3DB, $E9:0000)
    "FARM": 0x2907C1,           # 24 x 10 ($CF:0000, $E9:07C1); farm 24 is WRAM $A726 (the player's)
    "RACE_NAME_COUNT": 919,
    "RACE_COUNT": 1147,         # highest race number in the schedule + 1
    "GRADE_LIMITS": (18, 26),   # race_class
    "RACE_NAME": 0x276D74,      # 919 x 24 ($C4:C0C2, $E7:6D74)
    "RACE_SHORT": 0x2894D4,     # 919 x 12 ($C4:C070, $E8:94D4)
    "RACE": 0x28BFE8,           # 1147 x 6 ($C4:C5BB etc., $E8:BFE8)
    "SCHEDULE": 0x2AD534,       # 96 days x 63 ($C4:C225, $EA:D534)
    "VENUE": 0x1BC97,           # [3 slots][12 months] u16 course ($C4:C172)
    "MEETING": 0x1BCDF,         # [3 slots][12 months] u16 開催回 ($C4:C1CD)
    "DISTANCE": 0x1BD27,        # 16 x u16, x 100 m ($C4:C7C8)
    "SECRETARY": 0x1C211,       # 6 x 14
    "NICKNAME": 0x1C265,        # 6 x 3-byte pointers
    "FACE_PTR": 0x1BE8D,        # LZ pointer table (300 x 3); faces are entries 0-204
    "FACE_EXTRA": [0x2321F2, 0x2324D9, 0x2327A6],  # LZ streams of faces 205-207 (kind 7, kind 10 even / odd)
    "FACE_PALETTE": 0x1E52D,    # 6 x 32 bytes ($C1:0CCF)
    "STR": 0x1B6A4,             # string pointer tables below are relative to this
}
# string pointer tables (3-byte pointers), offset from "STR", count
STRINGS = {
    "stable": (0x10, 4), "area": (0x30, 4), "sex": (0x50, 3), "coat": (0x62, 8), "course": (0xA8, 16),
    "country": (0x148, 12), "local": (0x1A8, 4), "aptitude": (0x228, 8), "growth": (0x280, 4),
    "temper": (0x2A0, 4), "class": (0x2E0, 9), "class_short": (0x33C, 9), "surface": (0x381, 2),
    "surface_short": (0x391, 2), "going": (0x3B5, 5), "age": (0x3D9, 4), "weight": (0x3FD, 4),
    "region": (0x437, 10), "farm_suffix": (0x487, 8),
}

# Program '96: the copies at $C4:30D3 and the tables found from the code that reads them.
PROGRAM96 = {
    **ORIGINAL,
    "GLYPH_COUNT": 3277,
    "CHARSET": "charset_96.txt",
    "PERSON_PART": 0x29A41C,    # $E9:A41C
    "PERSON_PART_COUNT": 1014,
    "HORSE_PART": 0x270000,
    "RACEHORSE": 0x29D380,
    "INIT_687C": 0x2A82C8,
    "STALLION": 0x29E898,
    "MARE": 0x2AAFFA,
    "JOCKEY": 0x2ABBC6,
    "TRAINER": 0x28FF05,
    "OWNER": 0x2AC886,
    "INIT_A68B": 0x29FF63,
    "FOAL": 0x28FB70,
    "ROM_JOCKEY": 0x2ABFFE,     # $CC:415B, $EA:BFFE
    "FARM": 0x27FEFE,           # $E7:FEFE
    "RACE_NAME_COUNT": 930,
    "RACE_COUNT": 1162,         # race 0 is unused (FFFF), the schedule starts at race 1
    "GRADE_LIMITS": (17, 24),
    "RACE_NAME": 0x2A0000,      # 930 x 24 ($C7:009D, $EA:0000)
    "RACE_SHORT": 0x2A5730,     # 930 x 12 ($C7:004B, $EA:5730)
    "RACE": 0x28CBA0,           # $E8:CBA0
    "SECRETARY": 0x0BDB5F,
    "NICKNAME": 0x0BDBB3,
    "SCHEDULE": 0x29BBE0,       # $C7:0253, $E9:BBE0
    "VENUE": 0x0BD579,
    "MEETING": 0x0BD5C1,
    "DISTANCE": 0x0BD609,
    "FACE_PTR": 0x0BD781,
    "FACE_EXTRA": [0x232177, 0x23245E, 0x23272B],
    "FACE_PALETTE": 0x0AE939,
    "STR": 0x0BCF86,
}
VERSIONS = {"original": ORIGINAL, "program96": PROGRAM96}

HORSE_PART_COUNT = 6000                     # >= 6000: WRAM $A76E + 9 * (n - 6000), names the player typed
HORSE_PART_LIMIT = 0x189D                   # $C5:23EB: a word above this is an empty part
KATAKANA = "".join(chr(c) for c in range(ord("ァ"), ord("ヶ") + 1))

RACEHORSE_COUNT, RACEHORSE_SIZE = 140, 45     # slots; 120 horses (RACEHORSE_INIT)
RACEHORSE_INIT = 120                        # slots 120-139 are empty: FFFF in the original, cleared by $C4:31AB in '96
STALLION_COUNT, STALLION_SIZE = 255, 21
MARE_COUNT, MARE_SIZE = 140, 13
JOCKEY_COUNT, ROM_JOCKEY_COUNT, JOCKEY_SIZE = 60, 50, 18
TRAINER_COUNT, TRAINER_SIZE = 20, 12
OWNER_COUNT, OWNER_SIZE = 29, 15
FOAL_COUNT, FOAL_SIZE = 80, 7
FARM_COUNT, FARM_SIZE = 24, 10
SCHEDULE_DAYS, SCHEDULE_SIZE, SLOTS, RACES_PER_SLOT = 96, 63, 3, 10
SECRETARY_COUNT = 6

# The new-game copies ($C3:0F12): (key, WRAM address, length).
INIT_COPIES = [
    ("RACEHORSE", 0x488D, 0x189C), ("INIT_687C", 0x687C, 0x123E), ("STALLION", 0x886D, 0x14EB),
    ("MARE", 0x7ABA, 0x71C), ("JOCKEY", 0x9D58, 0x438), ("TRAINER", 0x8492, 0xF0), ("OWNER", 0xA4D8, 0x1B3),
    ("INIT_A68B", 0xA68B, 0x7D), ("FOAL", 0x81D6, 0x230),
]
# Program '96 copies the same blocks to these WRAM addresses ($C4:30D3)
INIT_WRAM_96 = {"RACEHORSE": 0x488D, "INIT_687C": 0x687F, "STALLION": 0x87FC, "MARE": 0x7ABD, "JOCKEY": 0x9CE7,
                "TRAINER": 0x8495, "OWNER": 0xA467, "INIT_A68B": 0xA61A, "FOAL": 0x81D9}

# ---------------------------------------------------------------- faces
# 40 x 48 = 5 x 6 4bpp tiles row-major (960 bytes): LZ entries 0-204 of the pointer table (face codes 0-204) and
# three streams of their own (codes 205-207). The face of a person is picked by kind and id, in the dialog face
# $CC:0C67(..., id, kind) and the same way in $C5:0019; the palette is $C1:E52D + 32 p.
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
FACE_COUNT = 208                            # Program '96: 235 (FACE_COUNT_96)
FACE_COUNT_96 = 235
PALETTE_COUNT = 6
# kind: (first code, codes, palette, label)
FACE_KINDS = {
    1: (0, 12, 4, "秘書"),                  # 2 * secretary + (year >= 15)
    2: (12, 122, 0, "騎手"),                # 2 * jockey + (age >= 35); palette 0, or 1 for the older face
    "2f": (134, 6, 0, "騎手"),              # women jockeys in slots 0x38, 0x19, 0x32, 0x11 by year ($C5:1F64)
    3: (140, 32, 2, "調教師"),              # trainer, successors by year ($C5:2051)
    4: (172, 28, 3, "馬主"),                # id % 28
    5: (200, 5, 5, "其他"),                 # id % 5
    7: (205, 1, 3, "其他"),
    10: (206, 2, 4, "其他"),                # id & 1
    # Program '96 only: LZ entries 294-320 of its pointer table
    "3n": (208, 4, 2, "調教師"),            # successors of trainers 12, 17, 14, 11 ($CB:05D6 100-103)
    "2s": (212, 3, 0, "騎手"),              # jockeys 8 and 14 up to year 15, jockey 46 up to year 13
    "2n": (215, 20, 0, "騎手"),             # 10 jockeys' later faces ($C5:0019), 2 each: palette 0 / 1 by age
}
FACE_PTR_96_EXTRA = 294                     # face code 208 + k is LZ entry 294 + k in Program '96
# $C5:2051: trainer id -> (year from which, successor face) ; other ids keep face id
TRAINER_SUCCESSOR = {0: [(13, 0x19)], 1: [(21, 0x1A), (3, 0x1B)], 2: [(25, 0x18)], 3: [(27, 0x17)], 4: [(8, 0x14)],
                     5: [(24, 0x16)], 7: [(2, 0x15)], 10: [(15, 0x1E)], 11: [(23, 0x1F)], 13: [(10, 0x1C)],
                     19: [(12, 0x1D)]}
# Program '96 $CB:05D6: trainer id -> (year from which, successor); 100-103 are the new faces (codes 208-211).
# (Trainer 9 has a block for year 25 that keeps his own face.)
TRAINER_SUCCESSOR_96 = {0: (3, 0x15), 1: (2, 0x1B), 2: (28, 0x17), 3: (19, 0x18), 4: (6, 0x14), 5: (10, 0x19),
                        7: (21, 0x16), 8: (18, 0x1A), 10: (16, 0x1F), 11: (8, 103), 12: (26, 100), 13: (7, 0x1C),
                        14: (23, 102), 17: (27, 101), 18: (12, 0x1E), 19: (9, 0x1D)}
# Program '96 $C5:0019 (tables $C5:E6DF / $C5:E6F3): jockey id, year from which he has a new face (codes 215 + 2 n)
JOCKEY_NEW_FACE_96 = [(20, 1), (15, 1), (48, 2), (0, 3), (27, 4), (37, 4), (18, 5), (31, 6), (53, 7), (19, 8)]


def face_kind(code: int):
    for k, (first, n, _, _) in FACE_KINDS.items():
        if first <= code < first + n:
            return k
    raise ValueError(code)


def face_palette_number(code: int) -> int:
    k = face_kind(code)
    if k in (2, "2n"):
        return (code - FACE_KINDS[k][0]) & 1
    return FACE_KINDS[k][2]


def women_jockey_96(i: int, year: int) -> int | None:
    """Program '96 $CB:0365 / $CB:04CF and the special cases of the dialog face: face code or None."""
    if i in (8, 14) and year <= 15:
        return FACE_KINDS["2s"][0] + (i == 14)
    if i == 0x2E:
        return FACE_KINDS["2s"][0] + 2 if year <= 13 else FACE_KINDS["2f"][0] + 2
    f = {0x38: 0 if year <= 14 else None, 0x13: 1 if 8 <= year <= 22 else None, 0x1A: 3 if year >= 13 else None,
         0x1D: 4 if year >= 14 else None, 0x2A: 5 if year >= 22 else None}.get(i)
    return None if f is None else FACE_KINDS["2f"][0] + f


def face_code(kind: int, i: int, year: int = 0, age: int = 0, version: str = "original") -> int | None:
    """$CC:0C67 / $C5:0019: the face code of person `i` of `kind` (age only for jockeys, year = WRAM $8583).
    Program '96 ($C8:0C67, year WRAM $8586) picks jockeys and trainers differently."""
    if kind == 1:
        return 2 * i + (year >= 15)
    if kind == 2 and version == "program96":
        if i == 0xFFFE:
            return FACE_KINDS["2n"][0] + 1
        f = women_jockey_96(i, year)
        if f is not None:
            return f
        for n, (j, y) in enumerate(JOCKEY_NEW_FACE_96):
            if i == j and year >= y:
                return FACE_KINDS["2n"][0] + 2 * n + (age >= 35)
        return FACE_KINDS[2][0] + 2 * i + (age >= 35)
    if kind == 2:
        f = None
        if i == 0x38 and year <= 16:
            f = 0 if year <= 7 else 2
        elif i == 0x19 and year <= 19:
            f = 1 if year <= 9 else 3
        elif i == 0x32 and 16 <= year <= 24:
            f = 4
        elif i == 0x11 and year >= 24:
            f = 5
        else:
            return FACE_KINDS[2][0] + 2 * i + (age >= 35)
        return None if f is None else FACE_KINDS["2f"][0] + f
    if kind == 3 and version == "program96":
        y, f = TRAINER_SUCCESSOR_96.get(i, (99, i))
        f = f if year >= y else i
        return FACE_KINDS["3n"][0] + f - 100 if f >= 100 else FACE_KINDS[3][0] + f
    if kind == 3:
        for y, f in TRAINER_SUCCESSOR.get(i, []):
            if year >= y:
                return FACE_KINDS[3][0] + f
        return FACE_KINDS[3][0] + i
    if kind == 4:
        return FACE_KINDS[4][0] + i % 28
    if kind == 5:
        return FACE_KINDS[5][0] + i % 5
    if kind == 7:
        return FACE_KINDS[7][0]
    if kind == 10:
        return FACE_KINDS[10][0] + (i & 1)
    return None


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return tuple(((c >> s) & 31) * 255 // 31 for s in (0, 5, 10))


def decode_tile(b: bytes) -> list[int]:
    """One 8x8 4bpp SNES tile -> 64 colour indices, row-major."""
    return [((b[2 * y] >> (7 - x)) & 1) | ((b[2 * y + 1] >> (7 - x)) & 1) << 1
            | ((b[16 + 2 * y] >> (7 - x)) & 1) << 2 | ((b[17 + 2 * y] >> (7 - x)) & 1) << 3
            for y in range(8) for x in range(8)]


def tiles_pixels(data: bytes) -> list[int]:
    """30 tiles (5 x 6) -> 40 x 48 colour indices, row-major."""
    w = FACE_W * 8
    px = [0] * (w * FACE_H * 8)
    for t in range(FACE_W * FACE_H):
        tile = decode_tile(data[32 * t:32 * t + 32])
        tx, ty = t % FACE_W * 8, t // FACE_W * 8
        for i, v in enumerate(tile):
            px[(ty + i // 8) * w + tx + i % 8] = v
    return px


# ---------------------------------------------------------------- text
GLYPH_W = GLYPH_H = 12
GLYPH_BYTES = 18


def glyph_code(code: int, count: int = ORIGINAL["GLYPH_COUNT"]) -> int:
    """$C1:6030: codes past the font are 0x91xx escapes (0x9140 + k -> 0x8200 + 0x100 k) or blank (0x8140)."""
    if code < 0x8140 + count:
        return code
    return (0x8200 + ((code - 0x9140) << 8)) & 0xFFFF if code >= 0x9140 else 0x8140


def load_charset(name: str = ORIGINAL["CHARSET"]) -> str:
    with open(os.path.join(HERE, "data", name), encoding="utf-8") as f:
        return "".join(line.rstrip("\n") for line in f if not line.startswith("#"))


def horse_part_text(b: bytes) -> str:
    """$C5:22A4: up to 9 bytes; 0xFE = ー, 0x00-0x6F = katakana ァ + b, anything else ends the part."""
    out = []
    for c in b[:9]:
        if c == 0xFE:
            out.append("ー")
        elif c < 0x70:
            out.append(KATAKANA[c])
        else:
            break
    return "".join(out)


def bits(v: int, shift: int, width: int) -> int:
    return v >> shift & ((1 << width) - 1)


def race_class(code: int, g2: int = 18, g1: int = 26) -> int:
    """$C4:C48C: race grade code (race +2 bits 0-4) -> class 0-8 (新馬 ... ＧⅠ); codes 9.. are ＧⅢ below g2, ＧⅡ
    below g1 (Program '96 $C7:04EC: 17 / 24)."""
    if code < 3:
        return code
    if code < 5:
        return code - 1
    if code < 8:
        return code - 2
    if code < 9:
        return code - 3
    return 6 if code < g2 else 7 if code < g1 else 8


def read_rom(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]


def detect_version(data: bytes) -> str:
    """Header title: "Winning Post 2" or "WinningPost2ﾌﾟﾛｸﾞﾗﾑ96" (half-width katakana, JIS X 0201)."""
    return "program96" if data[0xFFC0:0xFFD5].endswith(b"96") else "original"


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = read_rom(path)
        self.version = detect_version(self.data)
        self.revision = self.data[0xFFDB]          # header version byte: Program '96 Rev 1 = 1 (same offsets)
        self.o = VERSIONS[self.version]
        self.glyph_count = self.o["GLYPH_COUNT"]
        self.face_count = FACE_COUNT_96 if self.version == "program96" else FACE_COUNT
        self.charset = load_charset(self.o["CHARSET"])
        self.lz_tables = koei_lz.find_tables(self.data)

    # ------------------------------------------------------------ basics
    def u16(self, o: int) -> int:
        return self.data[o] | self.data[o + 1] << 8

    def ptr(self, o: int) -> int:
        return int.from_bytes(self.data[o:o + 3], "little") & 0x3FFFFF

    def lz(self, p: int) -> bytes:
        return koei_lz.decompress(self.data, p, self.lz_tables)[0]

    def record(self, key: str, i: int, size: int) -> bytes:
        o = self.o[key] + size * i
        return self.data[o:o + size]

    def glyph_offset(self, code: int) -> int:
        return self.o["FONT"] + GLYPH_BYTES * (glyph_code(code, self.glyph_count) - 0x8140)

    def text_bytes(self, d: bytes) -> str:
        """Game string: lead 0x81-0x9F = code 0x8140 + glyph (0x91 xx escapes, glyph_code); 0x0A = new line;
        0 ends; other single bytes are shown as [xx]."""
        cs = self.charset
        out, i = [], 0
        while i < len(d) and d[i]:
            c = d[i]
            nxt = d[i + 1] if i + 1 < len(d) else 0
            if 0x81 <= c <= 0x9F and i + 1 < len(d):
                g = glyph_code(c << 8 | nxt, self.glyph_count) - 0x8140
                out.append(cs[g] if 0 <= g < len(cs) else f"[{c:02X}{nxt:02X}]")
                i += 2
            elif c == 0x0A:
                out.append("\n")
                i += 1
            elif 0x20 <= c < 0x7F:
                out.append(chr(c))
                i += 1
            else:
                out.append(f"[{c:02X}]")
                i += 1
        return "".join(out)

    def text(self, o: int, limit: int = 256) -> str:
        return self.text_bytes(self.data[o:o + limit])

    def strings(self, key: str) -> list[str]:
        """A string pointer table (STRINGS)."""
        off, n = STRINGS[key]
        base = self.o["STR"] + off
        return [self.text(self.ptr(base + 3 * i), 40) for i in range(n)]

    def string_tables(self) -> dict[str, list[str]]:
        return {k: self.strings(k) for k in STRINGS}

    # ------------------------------------------------------------ names
    def person_part(self, n: int) -> str:
        """Name part n ($EA:AD39 + 6n): up to 3 glyph codes, not necessarily 0-terminated; 0xFFFF = none."""
        if n >= self.o["PERSON_PART_COUNT"]:
            return ""
        return self.text(self.o["PERSON_PART"] + 6 * n, 6)

    def horse_part(self, n: int) -> str:
        """$C5:23EB: n > 0x189D is empty; n >= 6000 is a name the player typed (WRAM)."""
        if n > HORSE_PART_LIMIT:
            return ""
        if n >= HORSE_PART_COUNT:
            return f"<user {n - HORSE_PART_COUNT}>"
        o = self.o["HORSE_PART"] + 9 * n
        return horse_part_text(self.data[o:o + 9])

    def horse_name(self, a: int, b: int) -> str:
        """$C5:246C: part a + part b, cut at 9 characters (byte 18 of the buffer is set to 0)."""
        return (self.horse_part(a) + self.horse_part(b))[:9]

    def _person(self, b: bytes) -> dict:
        w0, w1 = self.u16_of(b, 0), self.u16_of(b, 2)
        return {"surname": self.person_part(w0), "given": self.person_part(w1), "name_parts": f"{w0} {w1}"}

    @staticmethod
    def u16_of(b: bytes, o: int) -> int:
        return b[o] | b[o + 1] << 8

    # ------------------------------------------------------------ horses
    def stallion_name(self, i: int) -> str:
        if i >= STALLION_COUNT:
            return ""
        b = self.record("STALLION", i, STALLION_SIZE)
        return self.horse_name(self.u16_of(b, 0), self.u16_of(b, 2))

    def mare_name(self, i: int) -> str:
        if i >= MARE_COUNT:
            return ""
        b = self.record("MARE", i, MARE_SIZE)
        return self.horse_name(self.u16_of(b, 0), self.u16_of(b, 2))

    def mare_damsire(self, i: int) -> int:
        return self.record("MARE", i, MARE_SIZE)[4] if i < MARE_COUNT else 0xFF

    def farm_name(self, i: int) -> str:
        """$CF:0044: 3 characters + suffix (STRINGS farm_suffix, record +8 bits 6-7)."""
        if i >= FARM_COUNT:
            return ""
        b = self.record("FARM", i, FARM_SIZE)
        return self.text_bytes(b[:6]) + self.strings("farm_suffix")[bits(b[8], 6, 2)]

    def racehorses(self) -> list[dict]:
        """WRAM $488D initial racehorses. Accessors in bank $C4: +4 sire ($C4:2F7B), +5 dam ($C4:3036), +6 bits
        0-4 owner, 5-9 trainer ($C4:37F6), 10-14 farm ($C4:3749), +8 bits 4-6 age ($C4:399C), 10-11 sex ($C4:359B),
        +22 bits 13-15 coat ($C4:3A9D, $C5:1CED). Only slots 0-119 are horses (RACEHORSE_INIT)."""
        sex, coat = self.strings("sex"), self.strings("coat")
        owners = self.owners()
        trainers = self.trainers()
        out = []
        for i in range(RACEHORSE_INIT):
            b = self.record("RACEHORSE", i, RACEHORSE_SIZE)
            w6, w8, w22 = self.u16_of(b, 6), self.u16_of(b, 8), self.u16_of(b, 22)
            sire, dam = b[4], b[5]
            owner, trainer, farm = bits(w6, 0, 5), bits(w6, 5, 5), bits(w6, 10, 5)
            sx = bits(w8, 10, 2)
            out.append({
                "index": i, "name": self.horse_name(self.u16_of(b, 0), self.u16_of(b, 2)),
                "name_parts": f"{self.u16_of(b, 0)} {self.u16_of(b, 2)}",
                "age": bits(w8, 4, 3), "sex": sex[sx] if sx < 3 else "", "coat": coat[bits(w22, 13, 3)],
                "sire": sire, "sire_name": self.stallion_name(sire), "dam": dam, "dam_name": self.mare_name(dam),
                "damsire": self.mare_damsire(dam), "damsire_name": self.stallion_name(self.mare_damsire(dam)),
                "farm": farm, "farm_name": self.farm_name(farm),
                "owner": owner, "owner_name": owners[owner]["surname"] + owners[owner]["given"] if owner < OWNER_COUNT else "",
                "trainer": trainer,
                "trainer_name": trainers[trainer]["surname"] + trainers[trainer]["given"] if trainer < TRAINER_COUNT else "",
                "prize": self.u16_of(b, 10), "earnings": self.u16_of(b, 12),
                "record": "-".join(str(x) for x in b[16:20]),
                "data": b.hex(" "),
            })
        return out

    def stallions(self) -> list[dict]:
        """WRAM $886D: 255 slots; 0-146 are used at the start (11 of them have no name: name parts 0xFFFF), a free
        slot is 0xFF in +0-3 and +6-9."""
        out = []
        for i in range(STALLION_COUNT):
            b = self.record("STALLION", i, STALLION_SIZE)
            if b[0:4] == b"\xff" * 4 and b[6:10] == b"\xff" * 4:
                continue
            out.append({"index": i, "name": self.stallion_name(i),
                        "name_parts": f"{self.u16_of(b, 0)} {self.u16_of(b, 2)}", "data": b.hex(" ")})
        return out

    def mares(self) -> list[dict]:
        """WRAM $7ABA: +4 damsire (stallion, $C4:72C7)."""
        out = []
        for i in range(MARE_COUNT):
            b = self.record("MARE", i, MARE_SIZE)
            out.append({"index": i, "name": self.mare_name(i), "name_parts": f"{self.u16_of(b, 0)} {self.u16_of(b, 2)}",
                        "sire": b[4], "sire_name": self.stallion_name(b[4]), "data": b.hex(" ")})
        return out

    def foals(self) -> list[dict]:
        """WRAM $81D6 (80 x 7, no names): +0 dam (mare), +1 sire (stallion); the rest is not decoded."""
        out = []
        for i in range(FOAL_COUNT):
            b = self.record("FOAL", i, FOAL_SIZE)
            out.append({"index": i, "dam": b[0], "dam_name": self.mare_name(b[0]), "sire": b[1],
                        "sire_name": self.stallion_name(b[1]), "data": b.hex(" ")})
        return out

    # ------------------------------------------------------------ people
    def jockey_record(self, i: int) -> bytes:
        """$C4:A3DB: ids 0-59 are WRAM $9D58, 60- are ROM $E9:0000 + 18 (id - 60)."""
        if i < JOCKEY_COUNT:
            return self.record("JOCKEY", i, JOCKEY_SIZE)
        return self.record("ROM_JOCKEY", i - JOCKEY_COUNT, JOCKEY_SIZE)

    def jockeys(self) -> list[dict]:
        """+4 bits 0-6 age ($C4:A818), +7 u16 wins (推定), +13 ability (推定). Ids 60-89 are foreign (a katakana name
        split in two parts), 90-109 debut later."""
        out = []
        for i in range(JOCKEY_COUNT + ROM_JOCKEY_COUNT):
            b = self.jockey_record(i)
            p = self._person(b)
            foreign = 60 <= i < 90
            out.append({"index": i, "name": p["surname"] + ("" if foreign else " ") + p["given"],
                        "surname": p["surname"], "given": p["given"], "name_parts": p["name_parts"],
                        "source": "WRAM $9D58" if i < JOCKEY_COUNT else "ROM",
                        "age": b[4] & 0x7F, "wins": self.u16_of(b, 7), "ability": b[13],
                        "face": face_code(2, i, 0, b[4] & 0x7F, self.version) if i <= 60 else "", "data": b.hex(" ")})
        return out

    def trainers(self) -> list[dict]:
        """+4 bits 0-5 age - 40 ($C4:AFA7), bit 7 ($C4:AEF3: 栗東, 推定), +9 jockey (専属騎手), +10 jockey (2nd)."""
        out = []
        for i in range(TRAINER_COUNT):
            b = self.record("TRAINER", i, TRAINER_SIZE)
            p = self._person(b)
            out.append({"index": i, **p, "age": (b[4] & 0x3F) + 40, "stable": self.strings("stable")[b[4] >> 7],
                        "flag6": b[4] >> 6 & 1, "jockey": b[9], "jockey2": b[10] if b[10] != 0xFF else "",
                        "face": FACE_KINDS[3][0] + i, "data": b.hex(" ")})
        return out

    def owners(self) -> list[dict]:
        """WRAM $A4D8 (馬主・生産者): +4 bits 0-4 farm, +12 u16 funds (万円, 推定); the last is the player."""
        out = []
        for i in range(OWNER_COUNT):
            b = self.record("OWNER", i, OWNER_SIZE)
            p = self._person(b)
            w4 = self.u16_of(b, 4)
            farm = bits(w4, 0, 5)
            out.append({"index": i, **p, "farm": farm if farm < FARM_COUNT else "",
                        "farm_name": self.farm_name(farm), "funds": self.u16_of(b, 12),
                        "face": FACE_KINDS[4][0] + i % 28 if i < OWNER_COUNT - 1 else "", "data": b.hex(" ")})
        return out

    def farms(self) -> list[dict]:
        """$E9:07C1 x 10: +0 3 characters, +6 person part of the farm manager's surname, +8 bits 6-7 suffix,
        +9 region (STRINGS region)."""
        region = self.strings("region")
        out = []
        for i in range(FARM_COUNT):
            b = self.record("FARM", i, FARM_SIZE)
            out.append({"index": i, "name": self.farm_name(i), "manager": self.person_part(self.u16_of(b, 6)),
                        "region": region[b[9]] if b[9] < len(region) else b[9], "flags": b[8] & 0x3F,
                        "data": b.hex(" ")})
        return out

    def secretaries(self) -> list[dict]:
        out = []
        for i in range(SECRETARY_COUNT):
            o = self.o["SECRETARY"] + 14 * i
            b = self.data[o:o + 14]
            out.append({"index": i, "surname": self.text_bytes(b[:6]), "given": self.text_bytes(b[6:12]),
                        "sex": "女" if b[12] & 0x80 else "男", "age": b[12] & 0x7F, "salary": b[13],
                        "nickname": self.text(self.ptr(self.o["NICKNAME"] + 3 * i), 20),
                        "face": FACE_KINDS[1][0] + 2 * i, "face_later": FACE_KINDS[1][0] + 2 * i + 1})
        return out


    # ------------------------------------------------------------ races
    def race_name(self, n: int) -> str:
        return self.text(self.o["RACE_NAME"] + 24 * n, 24) if n < self.o["RACE_NAME_COUNT"] else ""

    def race_short(self, n: int) -> str:
        return self.text(self.o["RACE_SHORT"] + 12 * n, 12) if n < self.o["RACE_NAME_COUNT"] else ""

    def race(self, r: int) -> dict:
        """$E8:BFE8 + 6r: +0 name number, +2 bits 0-4 grade code (race_class), 5-8 distance ($C1:BD27), 9 芝,
        10 flag, 11-13 flags, 14-15 age condition; +4 bits 6-7 weight rule, 3-5 / 0-2 not decoded; +5 not decoded
        (0 for most races, non-zero for 特別 and graded races)."""
        b = self.record("RACE", r, 6)
        n, w2 = self.u16_of(b, 0), self.u16_of(b, 2)
        cls = race_class(bits(w2, 0, 5), *self.o["GRADE_LIMITS"])
        return {"race": r, "name_no": n, "name": self.race_name(n), "short": self.race_short(n),
                "class": self.strings("class")[cls], "grade_code": bits(w2, 0, 5),
                "surface": self.strings("surface")[bits(w2, 9, 1)],
                "distance": self.u16(self.o["DISTANCE"] + 2 * bits(w2, 5, 4)) * 100,
                "age": self.strings("age")[bits(w2, 14, 2)], "weight": self.strings("weight")[bits(b[4], 6, 2)],
                "flag10": bits(w2, 10, 1), "flags11": bits(w2, 11, 3), "b4_3": bits(b[4], 3, 3),
                "b4_0": bits(b[4], 0, 3), "b5": b[5], "data": b.hex(" ")}

    def races(self) -> list[dict]:
        return [self.race(r) for r in range(self.o["RACE_COUNT"])]

    def venue(self, slot: int, month: int) -> int:
        """$C4:C172: course of meeting slot 0-2 (east / west / local) in month 0-11, 0xFFFF = none."""
        return self.u16(self.o["VENUE"] + 24 * slot + 2 * month)

    def schedule(self) -> list[dict]:
        """$C4:C225: day = month * 8 + week * 2 + (day == 日曜); per day 3 slots x 10 races (u16, 0xFFFF none)."""
        course = self.strings("course")
        out = []
        for day in range(SCHEDULE_DAYS):
            month, rest = divmod(day, 8)
            week, sunday = divmod(rest, 2)
            base = self.o["SCHEDULE"] + SCHEDULE_SIZE * day
            for slot in range(SLOTS):
                v = self.venue(slot, month)
                for k in range(RACES_PER_SLOT):
                    r = self.u16(base + 20 * slot + 2 * k)
                    if r == 0xFFFF:
                        continue
                    out.append({"month": month + 1, "week": week + 1, "day": "日" if sunday else "土",
                                "slot": slot, "course": course[v] if v < len(course) else "",
                                "meeting": self.u16(self.o["MEETING"] + 24 * slot + 2 * month),
                                "race_no": k + 1, "race": r, "name": self.race_name(self.u16(self.o["RACE"] + 6 * r))})
        return out

    # ------------------------------------------------------------ faces
    def palette(self, n: int) -> list[int]:
        o = self.o["FACE_PALETTE"] + 32 * n
        return [self.u16(o + 2 * i) for i in range(16)]

    def face_pointer(self, code: int) -> int:
        if code >= FACE_COUNT:
            return self.ptr(self.o["FACE_PTR"] + 3 * (FACE_PTR_96_EXTRA + code - FACE_COUNT))
        if code >= FACE_KINDS[7][0]:
            return self.o["FACE_EXTRA"][code - FACE_KINDS[7][0]]
        return self.ptr(self.o["FACE_PTR"] + 3 * code)

    def face_bytes(self, code: int) -> bytes:
        return self.lz(self.face_pointer(code))[:FACE_BYTES]

    def face_rgb(self, code: int) -> list[list[tuple[int, int, int]]]:
        pal = [bgr555_rgb(c) for c in self.palette(face_palette_number(code))]
        px = tiles_pixels(self.face_bytes(code))
        w = FACE_W * 8
        return [[pal[v] for v in px[y * w:(y + 1) * w]] for y in range(FACE_H * 8)]
