"""SFC 麻雀大会II (KOEI) ROM decoding.

Offsets are file offsets of the headerless 1 MB LoROM image (CPU $BB:8000-$BB:FFFF = file BB * 0x8000 + addr - 0x8000).
Data streams are KOEI LZ (tools/koei_lz.py), addressed by inline pointers in the code (LDA #bank, PEA src, PEA dst,
JSL $01:8000) or by the tables below. Opponents are numbered 1-26 (0 is the player). See docs/ROM_FORMAT.md.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz
from replay import load_rom_bytes

DEFAULT_ROM = os.path.join(REPO, "roms", "Mahjong Taikai II (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")
GLYPH16 = os.path.join(HERE, "data", "glyph16.txt")
PERSONS_TSV = os.path.join(HERE, "data", "persons.tsv")
RULES_TSV = os.path.join(HERE, "data", "rules.tsv")

PERSON_COUNT = 26
PERSONS = range(1, PERSON_COUNT + 1)
PARLOR_PERSONS = range(1, 24)   # 24-26 (織田信長, 諸葛孔明, シブサワ・コウ) only play in the 大会 finals

# Faces: one stream per opponent (3-byte pointers at $01:CF9B + 3p), 7968 bytes = nine images of 4bpp tiles, row-major:
# 0-6 at 800k (40x40, 5x5 tiles), 7 at 5600 (56x56, 7x7 tiles, 1568 bytes), 8 at 7168 (40x40)
FACE_PTRS = 0xCF9B
FACE_IMAGES = [(800 * k, 5) for k in range(7)] + [(5600, 7), (7168, 5)]
FACE_LABELS = ["平常", "說話 1", "說話 2", "笑", "困", "哭", "不滿", "怒", "驚"]   # 1-2: mouth frames of the talking face
BIG_IMAGE = 7
# Palettes: 32 bytes each at $02:8000 + 32k. Face palette of opponent p: $01:CCB1 + p - 1; the 56x56 image uses
# $01:CCCB + p - 1 instead (loaded into CGRAM row 15 when a line shows it)
PALETTES = 0x10000
FACE_PAL = 0xCCB1
BIG_PAL = 0xCCCB
# Dialogue: a line's first byte (0-6) picks the image shown next to it: $01:D5B0 = offsets in the WRAM copy of the face
# stream ($7F:1000 + offset)
DIALOGUE_FACE_OFFSET = 0xD5B0
DIALOGUE_FACE_COUNT = 7

# Name graphics: stream 04:C951, 26 x 512 bytes = 8 x 2 tiles (64x16, top row then bottom row)
NAME_STREAM = 0x04C951
NAME_W, NAME_H = 8, 2
NAME_BYTES = 512

# Playing parameters: 12 bytes per person at $01:DA92 + 12p (p = 0 is the player's auto play), expanded by $01:C999
# into 22 nibbles (bytes 0-10, high nibble first) and 8 flags (byte 11)
PARAMS = 0xDA92
PARAM_SIZE = 12
# Parlor of the persons 1-23 at $01:D41C + p: 0 = plays in every parlor, k = only in parlor k (its host)
PERSON_PARLOR = 0xD41C
PARLOR_COUNT = 7

# Dialogue: per opponent one stream (LE16 address at $01:D5BE + 2(p-1), bank at $01:D5F2 + p-1) of 344 lines x 25 bytes:
# face code, then 24 font codes (3 lines of 8; D4 = blank)
DIALOGUE_ADDR = 0xD5BE
DIALOGUE_BANK = 0xD5F2
LINE_COUNT, LINE_SIZE = 344, 25
BLANK = 0xD4
# Situations 0-102: first line ($01:D60C, LE16), chance ($01:D6DA: the line is first + random(n); none when that
# reaches the next situation's first line), flags ($01:D741)
SITUATION_COUNT = 103
SITUATION_START = 0xD60C
SITUATION_CHANCE = 0xD6DA
SITUATION_FLAGS = 0xD741

# Dialogue font: 8x16 glyphs (two 4bpp tiles, top then bottom), codes 01-D4 in stream 03:F630 at 64 * (code - 1)
FONT_STREAM = 0x03F630
FONT_CODES = 0xD4

# Yaku and other score-screen names: strings at $01:F4BD of 16x16 glyph numbers + 1, each ended by 0 (drawn by
# $00:8B16); glyphs: stream 04:AD49, 108 x 128 bytes (2 x 2 4bpp tiles: TL, TR, BL, BR)
YAKU_NAMES = 0xF4BD
YAKU_COUNT = 54          # 0-53 are yaku; 54-58 limit hands, 59 荒牌, 60-64 abortive draws
NAME_STRINGS = 65
GLYPH16_STREAM = 0x04AD49
GLYPH16_COUNT = 108

# Rules: 44 items, a rule set is 22 bytes of nibbles (high first): standard set $01:D382; three sets in WRAM $192F + 22k
# (SRAM); values per item $01:D356; parlor overrides $01:D398 (offset per parlor) -> $01:D39F (item, value) pairs ended
# by 0; dependencies $01:D3F1 (13 pairs: item A == 0 forces item B = 0); 持ち点 in hundreds at $01:D339 (LE16)
RULE_ITEMS = 44
RULE_COUNTS = 0xD356
RULE_STANDARD = 0xD382
RULE_OVERRIDE_START = 0xD398
RULE_OVERRIDES = 0xD39F
RULE_DEPS = 0xD3F1
RULE_DEP_COUNT = 13
STARTING_POINTS = 0xD339
STARTING_POINTS_ITEM = 10

# System messages: $01:DDFC, numbered from 1, each ended by 0: a header (4 bytes; + 2 if bit 0, + 2 if bit 1 of the
# first byte; 6 if bit 7) and font codes (D5 = new line, DA = new page, D6-D9 = choices / numbers)
MESSAGES = 0xDDFC
MESSAGE_COUNT = 71
PROFILE_MESSAGE = 48     # message 48 + p = profile of opponent p (1-23)


def lorom(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


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


def tiles_to_pixels(tiles: bytes, w: int, h: int) -> list[int]:
    """w x h tiles stored row-major -> (8w x 8h) colour numbers, row-major."""
    out = [0] * (w * h * 64)
    for t in range(w * h):
        for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
            out[(t // w * 8 + i // 8) * w * 8 + t % w * 8 + i % 8] = v
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    """SNES colour -> 8-bit RGB (5-bit value << 3 | value >> 2, as Mesen shows it)."""
    return tuple((c >> s & 31) << 3 | (c >> s & 31) >> 2 for s in (0, 5, 10))


def read_tsv(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        rows = [line.rstrip("\n").split("\t") for line in f if not line.startswith("#") and line.strip()]
    head = rows[0]
    return [dict(zip(head, r + [""] * (len(head) - len(r)))) for r in rows[1:]]


def load_charset(path: str = CHARSET) -> dict[int, str]:
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip("\n"):
                continue
            code, ch = line.rstrip("\n").split("\t")
            out[int(code, 16)] = ch
    assert sorted(out) == list(range(FONT_CODES)), len(out)
    return out


def load_glyph16(path: str = GLYPH16) -> str:
    with open(path, encoding="utf-8") as f:
        out = "".join(line.rstrip("\n").split("\t")[1] for line in f if not line.startswith("#") and line.strip())
    assert len(out) == GLYPH16_COUNT, len(out)
    return out


def message_header_size(first: int) -> int:
    return 6 if first & 0x80 else 4 + 2 * (first & 1) + 2 * (first >> 1 & 1)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.tables = koei_lz.find_tables(self.data)
        self.charset = load_charset()
        self.glyphs16 = load_glyph16()
        self._cache: dict[int, bytes] = {}

    def stream(self, addr: int) -> bytes:
        """Decompressed LZ stream at CPU address addr."""
        if addr not in self._cache:
            self._cache[addr] = koei_lz.decompress(self.data, lorom(addr), self.tables)[0]
        return self._cache[addr]

    def long_ptr(self, at: int) -> int:
        return int.from_bytes(self.data[at:at + 3], "little")

    # --- text ---
    def char(self, c: int) -> str:
        return " " if c == BLANK else self.charset.get(c, f"[{c:02X}]")

    def text(self, codes: bytes, width: int = 8) -> str:
        """Font codes -> str, a newline every `width` codes; D4 = blank (trailing blanks dropped)."""
        lines = ["".join(self.char(c) for c in codes[i:i + width]).rstrip(" ") for i in range(0, len(codes), width)]
        return "\n".join(lines).rstrip("\n")

    def glyph(self, code: int) -> bytes:
        """64 bytes: the two 4bpp tiles (top, bottom) of font code 01-D4."""
        return self.stream(FONT_STREAM)[64 * (code - 1):64 * code]

    # --- persons ---
    def persons(self) -> list[dict]:
        names = {int(r["id"]): r for r in read_tsv(PERSONS_TSV)}
        out = []
        for p in PERSONS:
            out.append({"id": p, "name": names[p]["名前"], "reading": names[p]["読み"], "origin": names[p]["[EXT]出典"],
                        "face_stream": self.long_ptr(FACE_PTRS + 3 * p),
                        "palette": self.data[FACE_PAL + p - 1], "big_palette": self.data[BIG_PAL + p - 1],
                        "dialogue_stream": self.dialogue_addr(p), "parlor": self.parlor(p),
                        "params": self.params(p), "profile": self.profile(p)})
        return out

    def parlor(self, p: int) -> int | None:
        """0 = every parlor, k = parlor k only, None = no parlor (persons 24-26)."""
        return self.data[PERSON_PARLOR + p] if p in PARLOR_PERSONS else None

    def parlor_persons(self, k: int) -> list[int]:
        """Opponents listed in parlor k (all have money; $00:AF13 also drops those with none)."""
        return [p for p in PARLOR_PERSONS if self.data[PERSON_PARLOR + p] in (0, k)]

    def params(self, p: int) -> dict:
        r = self.data[PARAMS + PARAM_SIZE * p:PARAMS + PARAM_SIZE * (p + 1)]
        nibbles = [n for b in r[:11] for n in (b >> 4, b & 15)]
        flags = [r[11] >> (7 - k) & 1 for k in range(8)]
        return {"raw": r, "nibbles": nibbles, "flags": flags}

    def profile(self, p: int) -> str:
        return self.message_text(PROFILE_MESSAGE + p) if p in PARLOR_PERSONS else ""

    # --- faces ---
    def palette(self, k: int) -> list[int]:
        return [le16(self.data, PALETTES + 32 * k + 2 * i) for i in range(16)]

    def image_palette(self, p: int, k: int) -> int:
        return self.data[(BIG_PAL if k == BIG_IMAGE else FACE_PAL) + p - 1]

    def face_stream(self, p: int) -> bytes:
        return self.stream(self.long_ptr(FACE_PTRS + 3 * p))

    def face_tiles(self, p: int, k: int) -> bytes:
        off, w = FACE_IMAGES[k]
        return self.face_stream(p)[off:off + 32 * w * w]

    def face_size(self, k: int) -> tuple[int, int]:
        return FACE_IMAGES[k][1], FACE_IMAGES[k][1]

    def face_pixels(self, p: int, k: int) -> list[int]:
        w, h = self.face_size(k)
        return tiles_to_pixels(self.face_tiles(p, k), w, h)

    def face_rgb(self, p: int, k: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.palette(self.image_palette(p, k))]
        return [pal[v] for v in self.face_pixels(p, k)]

    def dialogue_face_offsets(self) -> list[int]:
        """Offset in the face stream of the image each face code 0-6 shows."""
        return [le16(self.data, DIALOGUE_FACE_OFFSET + 2 * e) - 0x1000 for e in range(DIALOGUE_FACE_COUNT)]

    def dialogue_faces(self) -> list[int]:
        """Image number (0-8) for each face code 0-6 of a dialogue line."""
        offs = [o for o, _ in FACE_IMAGES]
        return [offs.index(o) for o in self.dialogue_face_offsets()]

    # --- names ---
    def name_tiles(self, p: int) -> bytes:
        return self.stream(NAME_STREAM)[NAME_BYTES * (p - 1):NAME_BYTES * p]

    def name_rgb(self, p: int) -> list[tuple[int, int, int]]:
        pal = [(16, 16, 96), (255, 255, 255), (255, 255, 0), (0, 0, 0)] + [(255, 0, 255)] * 12
        return [pal[v] for v in tiles_to_pixels(self.name_tiles(p), NAME_W, NAME_H)]

    # --- dialogue ---
    def situations(self) -> list[dict]:
        firsts = [le16(self.data, SITUATION_START + 2 * s) for s in range(SITUATION_COUNT)] + [LINE_COUNT]
        return [{"id": s, "first": firsts[s], "count": firsts[s + 1] - firsts[s],
                 "chance": self.data[SITUATION_CHANCE + s], "flags": self.data[SITUATION_FLAGS + s]}
                for s in range(SITUATION_COUNT)]

    def dialogue_addr(self, p: int) -> int:
        return le16(self.data, DIALOGUE_ADDR + 2 * (p - 1)) | self.data[DIALOGUE_BANK + p - 1] << 16

    def dialogue_raw(self, p: int) -> bytes:
        return self.stream(self.dialogue_addr(p))

    def dialogue(self, p: int) -> list[dict]:
        raw = self.dialogue_raw(p)
        faces = self.dialogue_faces()
        out = []
        for n in range(LINE_COUNT):
            r = raw[LINE_SIZE * n:LINE_SIZE * (n + 1)]
            out.append({"line": n, "face_code": r[0], "face": faces[r[0]] if r[0] < len(faces) else None,
                        "codes": r[1:], "text": self.text(r[1:])})
        return out

    # --- yaku ---
    def glyph16(self, g: int) -> bytes:
        return self.stream(GLYPH16_STREAM)[128 * g:128 * (g + 1)]

    def name_codes(self) -> list[bytes]:
        out, i = [], YAKU_NAMES
        for _ in range(NAME_STRINGS):
            j = self.data.index(0, i)
            out.append(self.data[i:j])
            i = j + 1
        return out

    def yaku(self) -> list[dict]:
        return [{"id": n, "codes": c, "name": "".join(self.glyphs16[b - 1] for b in c)}
                for n, c in enumerate(self.name_codes())]

    # --- rules ---
    def rule_items(self) -> list[dict]:
        rows = read_tsv(RULES_TSV)
        std = self.rule_nibbles(self.data[RULE_STANDARD:RULE_STANDARD + RULE_ITEMS // 2])
        out = []
        for i, r in enumerate(rows):
            labels = r["選項"].split("|")
            if i == STARTING_POINTS_ITEM:
                labels = [f"{le16(self.data, STARTING_POINTS + 2 * v) * 100:,}" for v in range(len(labels))]
            out.append({"id": i, "name": r["名前"], "count": self.data[RULE_COUNTS + i], "labels": labels,
                        "standard": std[i]})
        return out

    @staticmethod
    def rule_nibbles(raw: bytes) -> list[int]:
        return [n for b in raw for n in (b >> 4, b & 15)]

    def rule_overrides(self, k: int) -> list[tuple[int, int]]:
        y, out = self.data[RULE_OVERRIDE_START + k], []
        while self.data[RULE_OVERRIDES + y]:
            out.append((self.data[RULE_OVERRIDES + y], self.data[RULE_OVERRIDES + y + 1]))
            y += 2
        return out

    def rule_deps(self) -> list[tuple[int, int]]:
        return [(self.data[RULE_DEPS + 2 * i], self.data[RULE_DEPS + 2 * i + 1]) for i in range(RULE_DEP_COUNT)]

    def parlor_rules(self, k: int, rule_set: list[int] | None = None) -> list[int]:
        """Rules in force in parlor k ($01:8F8A in 雀荘 mode): parlor 1 uses the standard set, the others the player's
        rule set (default: the standard one) with the parlor's overrides; then the dependencies (deps go from the last
        pair to the first, as the game does)."""
        std = self.rule_nibbles(self.data[RULE_STANDARD:RULE_STANDARD + RULE_ITEMS // 2])
        out = list(std if k == 1 or rule_set is None else rule_set)
        if k != 1:
            for item, v in self.rule_overrides(k):
                out[item] = v
        for a, b in reversed(self.rule_deps()):
            if out[a] == 0:
                out[b] = 0
        return out

    def starting_points(self, v: int) -> int:
        return le16(self.data, STARTING_POINTS + 2 * v) * 100

    # --- messages ---
    def message_raw(self, n: int) -> tuple[bytes, bytes]:
        """(header, codes) of system message n (1-based)."""
        i = MESSAGES
        for _ in range(n - 1):
            i = self.data.index(0, i) + 1
        j = self.data.index(0, i)
        h = message_header_size(self.data[i])
        return self.data[i:i + h], self.data[i + h:j]

    def message_text(self, n: int) -> str:
        ctrl = {0xD5: "\n", 0xDA: "\n\n"}
        return "".join(ctrl.get(c, self.char(c) if c < FONT_CODES or c == BLANK else f"[{c:02X}]")
                       for c in self.message_raw(n)[1])
