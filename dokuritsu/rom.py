"""SFC 独立戦争 Liberty or Death (KOEI, 1994) ROM decoding.

Offsets are file offsets of the headerless 1.25 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
The LZ decompressor is the shared one in tools/koei_lz.py (table block at $C0:A0D9); LZ entry i is the stream
behind long pointer i of LZ_POINTERS ($C3:9649, 419 entries).
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Dokuritsu Sensou - Liberty or Death (Japan).zip")
LZ_TABLES = 0xA0D9
LZ_POINTERS = 0x39649
LZ_COUNT = 419

# Text: half-width kana (cp932 single bytes); ESC 'K' / ESC 'H' switch the same bytes to katakana / hiragana,
# ESC 'C' n sets the colour. 0x81-0x83 start a 2-byte kanji code of the game's own order (font not decoded);
# the codes below were read off the screen next to the strings that use them.
KANJI = {0x832F: "統", 0x83D0: "率", 0x83DC: "力", 0x82C0: "戦", 0x826F: "術", 0x8241: "指", 0x8336: "導",
         0x83A7: "名", 0x82AD: "声", 0x81DF: "軍"}

# Persons 0-249 (sorted by surname): 33 bytes, see Rom.persons. Accessor $C8:0BFD.
PERSONS = 0x1A7F7
PERSON_COUNT = 250
PERSON_SIZE = 33
STATS = ["体力", "統率力", "戦術力", "指導力"]  # +25..+28

# Locations 0-52: 25 bytes, see Rom.locations. Accessor $C8:0BA3. The game shows location id + 1.
LOCATIONS = 0x19178
LOCATION_COUNT = 53
LOCATION_SIZE = 25
REGIONS = ["北部", "中部", "南部"]
# 15 states (location +24 bits 2-5): abbreviations and full names, NUL-terminated strings behind long pointers
STATE_ABBR = 0x1D372
STATE_NAMES = 0x1D3CC
STATE_COUNT = 15

# The only scenario (1775). New game: $C8:17FC copies these ROM blocks to WRAM bank $7E.
SCENARIO_BLOCKS = [  # (ROM offset, WRAM address, length, meaning)
    (0x18D7C, 0x2009, 0x47, "未解（ff 35 00..34 ff ...）"),
    (0x18DC3, 0x2054, 0x41, "13 x 5 bytes，未解"),
    (0x18E04, 0x2095, 0x2E6, "地點狀態 53 x 14"),
    (0x190EA, 0x237B, 0x2C, "2 x 22 bytes，未解"),
    (0x19116, 0x23A7, 0x62, "陣營 2 x 49"),
    (0x19A4B, 0x2409, 0xDAC, "人物狀態 250 x 14"),
]
LOCATION_STATES, LOCATION_STATE_WRAM, LOCATION_STATE_SIZE = 0x18E04, 0x2095, 14
SIDES, SIDES_WRAM, SIDE_SIZE = 0x19116, 0x23A7, 49
PERSON_STATES, PERSON_STATE_WRAM, PERSON_STATE_SIZE = 0x19A4B, 0x2409, 14
RESERVE = 0x35          # person state +2: not at a location
SIDE_NAMES = ["アメリカ", "イギリス"]
# person state +6 high nibble (guess from the persons of each group)
FACTIONS = {0: "大陸軍(推測)", 1: "民兵(推測)", 2: "フランス(推測)", 3: "スペイン(推測)", 4: "イギリス(推測)",
            5: "王党派・インディアン(推測)"}

# Faces 40x48 = 5x6 4bpp tiles row-major (960 bytes), drawn by $C2:3FA8. Code bit 15 clear: portrait = LZ entry
# PORTRAIT_ENTRY + code (174 portraits, persons use 0-124). Bit 15 set: composed by $C2:3E66 / $C2:3ADA from
# uncompressed parts at file offset 0 (see Rom.face_tiles). All faces use the palette at FACE_PALETTE.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_ENTRY = 67
PORTRAIT_COUNT = 174
FACE_PALETTE = 0x39B72
PART_TILES = 0x18D35     # LE16 [type 0-3][part 0-4]: tiles of one variant
PART_SIZE = 0x2F811      # LE16 [type][part]: 10 * columns + rows
PART_POS = 0x2F839       # LE16 [type][part]: 10 * x + y (tiles)
PART_ORDER = [4, 0, 1, 2, 3]   # the game draws code digit k = 5, 1, 2, 3, 4 = part k - 1
TYPE_COUNT = 4

# Big map: 3 regions (北部 中部 南部) = LZ entries 16-18, 672 4bpp tiles each, shown as a sequential 28 x 24
# tile block (BG2, palette 3 = MAP_PALETTE). The game recolours colour 15 (the white land) of the tiles of
# each location by owner (to colour 8, 12 or 3); which pixels belong to which location is not decoded.
MAP_ENTRY = 16
MAP_W, MAP_H = 28, 24
MAP_PALETTE = 0x39C52

# Battle (HEX) maps: one per location, 14 columns x 12 rows of hexes, 2 bytes per cell (row-major).
# Layer A = LZ entry 1 after a 16-byte "LIBERTY_HEX_MAP" header, layer B = LZ entry 2; 336 bytes per map.
# A cell byte 0 bits 0-3 = terrain 0-10 (bits 4-7 and byte 1 unknown); B = 4 nibbles of the tiles of
# terrains 4, 5, 7 (8888 = plain tile, FFFF = none). The BG2 tilemap ($7F:8000, 32 x 28) is built by $C6:6CAB:
# hex (x, y) covers tiles (2x + 2, 2y + 2 + (1 if x even)) .. +1, see Rom.battle_cell_tiles.
BATTLE_A_ENTRY, BATTLE_B_ENTRY = 1, 2
BATTLE_HEADER = 16
BATTLE_W, BATTLE_H = 14, 12
BATTLE_MAP_BYTES = 2 * BATTLE_W * BATTLE_H
BATTLE_TILE_ENTRY = 241   # 71 tiles loaded at VRAM tile 0x2B9 (the tilemap entries are 0x1B9.. + 0x100)
BATTLE_TILE0 = 0x2B9
BATTLE_PLAIN = 0x1B9      # + 4 * terrain + (0 TL, 1 TR, 2 BL, 3 BR)
BATTLE_OVERLAY = {7: 0x1E5, 4: 0x1EE, 5: 0x1F7}   # + nibble k of B for tile k
BATTLE_PALETTE = 0x39DD2  # CGRAM palette 5 in battle (seen in 1775; seasons not checked)
BATTLE_TM_W, BATTLE_TM_H = 32, 28
# What the plain tiles of each terrain look like (names are guesses from the pictures; 6 is not used by any map)
TERRAIN_LOOKS = ["草地", "森林", "丘陵", "山", "河川", "淺灘", "（磚紋，未使用）", "海・湖", "城鎮", "要塞", "柵欄陣地"]


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


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


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]


def text(raw: bytes) -> str:
    """Game string -> str (full-width kana; unknown kanji as {XXXX}); stops at NUL."""
    out, i, hira = [], 0, False
    while i < len(raw) and raw[i]:
        c = raw[i]
        if c == 0x1B:
            if raw[i + 1] in (0x4B, 0x48):
                hira = raw[i + 1] == 0x48
                i += 2
            else:
                i += 3
        elif 0x81 <= c <= 0x83:
            code = c << 8 | raw[i + 1]
            out.append(KANJI.get(code, f"{{{code:04X}}}"))
            i += 2
        else:
            ch = unicodedata.normalize("NFKC", bytes([c]).decode("cp932", "replace"))
            if hira:
                ch = "".join(chr(ord(k) - 0x60) if "ァ" <= k <= "ヶ" else k for k in ch)
            out.append(ch)
            i += 1
    # NFKC per byte leaves the (han)dakuten as combining marks; NFC joins them to the kana before
    return unicodedata.normalize("NFC", "".join(out))


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        assert koei_lz.find_tables(self.data) == LZ_TABLES
        self._cache: dict[int, bytes] = {}

    # --- generic ---
    def ptr(self, table: int, i: int) -> int:
        return hirom(int.from_bytes(self.data[table + 3 * i:table + 3 * i + 3], "little"))

    def entry(self, i: int) -> bytes:
        """LZ entry i decompressed."""
        if i not in self._cache:
            self._cache[i] = koei_lz.decompress(self.data, self.ptr(LZ_POINTERS, i), LZ_TABLES)[0]
        return self._cache[i]

    def string(self, p: int) -> str:
        return text(self.data[p:self.data.index(b"\0", p) + 1])

    # --- master tables ---
    def persons(self) -> list[dict]:
        """+0 initial of the first name (ASCII) and 0, +2 first name (12), +14 surname (11), +25 体力 (start),
        +26 統率力 +27 戦術力 +28 指導力, +29 bits 0-1 = kind (0-3, 未解), bits 2-7 未解 (63 for most),
        +30 未解 (53 for most), +31 face code LE16."""
        out = []
        for pid in range(PERSON_COUNT):
            o = PERSONS + PERSON_SIZE * pid
            r = self.data[o:o + PERSON_SIZE]
            p = {"id": pid, "offset": o, "raw": r, "initial": chr(r[0]), "first": text(r[2:14]),
                 "last": text(r[14:25]), "kind": r[29] & 3, "unknown29": r[29] >> 2, "unknown30": r[30],
                 "face": le16(r, 31)}
            p["name"] = f"{p['first']}・{p['last']}"
            for k, s in enumerate(STATS):
                p[s] = r[25 + k]
            out.append(p)
        return out

    def states(self) -> list[dict]:
        out = []
        for i in range(STATE_COUNT):
            out.append({"id": i, "abbr": self.string(self.ptr(STATE_ABBR, i)),
                        "name": self.string(self.ptr(STATE_NAMES, i))})
        return out

    def locations(self) -> list[dict]:
        """+0 未解 (0-100), +1 flags (未解), +2 name (14), +16 neighbours (8, FF-padded),
        +24 bits 0-1 region, bits 2-5 state, bit 6 port (guess: set for the coastal places)."""
        out = []
        for i in range(LOCATION_COUNT):
            o = LOCATIONS + LOCATION_SIZE * i
            r = self.data[o:o + LOCATION_SIZE]
            out.append({"id": i, "no": i + 1, "offset": o, "raw": r, "unknown0": r[0], "flags": r[1],
                        "name": text(r[2:16]), "neighbours": [n for n in r[16:24] if n != 0xFF],
                        "region": r[24] & 3, "state": r[24] >> 2 & 15, "port": r[24] >> 6 & 1})
        return out

    # --- scenario (1775) ---
    def person_states(self) -> list[dict]:
        """14 bytes at $7E:2409 + 14 id: +0 next person of the same list (WRAM pointer, 0 end), +2 location
        (0x35 = none), +3 体力, +4 名声, +5 忠誠, +6 high nibble faction (推測), +7 bits 0-1 rank (推測) and
        flags, +8..+13 未解."""
        out = []
        for pid in range(PERSON_COUNT):
            o = PERSON_STATES + PERSON_STATE_SIZE * pid
            r = self.data[o:o + PERSON_STATE_SIZE]
            out.append({"id": pid, "raw": r, "next": le16(r, 0), "location": r[2], "体力": r[3], "名声": r[4],
                        "忠誠": r[5], "faction": r[6] >> 4, "unknown6": r[6] & 15, "rank": r[7] & 3,
                        "flags7": r[7] & 0xFC, "unknown8": r[8:14].hex()})
        return out

    @staticmethod
    def person_of(ptr: int) -> int:
        """WRAM pointer to a person state -> person id."""
        return (ptr - PERSON_STATE_WRAM) // PERSON_STATE_SIZE

    def person_list(self, head: int, states: list[dict] | None = None) -> list[int]:
        states = states or self.person_states()
        out = []
        while head and len(out) < PERSON_COUNT:
            pid = self.person_of(head)
            out.append(pid)
            head = states[pid]["next"]
        return out

    def location_states(self) -> list[dict]:
        """14 bytes at $7E:2095 + 14 id: +0 and +2 heads of person lists (equal at the start), +4 owner code
        (未解: 0 1 4 5 6), +5 支持, +6 食糧 LE16, +8 武器 LE16 (推測), +10 弾薬 LE16 (推測), +12 未解 (100)."""
        states = self.person_states()
        out = []
        for i in range(LOCATION_COUNT):
            o = LOCATION_STATES + LOCATION_STATE_SIZE * i
            r = self.data[o:o + LOCATION_STATE_SIZE]
            out.append({"id": i, "raw": r, "head0": le16(r, 0), "head2": le16(r, 2),
                        "persons": self.person_list(le16(r, 0), states), "owner": r[4], "支持": r[5],
                        "食糧": le16(r, 6), "武器": le16(r, 8), "弾薬": le16(r, 10), "unknown12": r[12],
                        "unknown13": r[13]})
        return out

    def sides(self) -> list[dict]:
        """49 bytes at $7E:23A7: +0 commander (WRAM person pointer, set when the game starts), +2 head of the
        list of persons not at a location, +5 LE16 = 500 (推測: 資金), the rest 0."""
        states = self.person_states()
        out = []
        for i in range(2):
            r = self.data[SIDES + SIDE_SIZE * i:SIDES + SIDE_SIZE * (i + 1)]
            out.append({"id": i, "name": SIDE_NAMES[i], "raw": r, "commander": le16(r, 0), "reserve": le16(r, 2),
                        "reserve_persons": self.person_list(le16(r, 2), states), "unknown4": r[4],
                        "funds": le16(r, 5)})
        return out

    # --- faces ---
    def face_palette(self) -> list[int]:
        return [le16(self.data, FACE_PALETTE + 2 * i) for i in range(16)]

    def part_base(self, t: int, p: int) -> int:
        """File offset of the 4 variants of part p of type t."""
        off = 0
        for k in range(5 * t + p):
            off += le16(self.data, PART_TILES + 2 * k) * 4 * 32
        return off

    def part_cells(self, t: int, p: int) -> list[tuple[int, int]]:
        """(source tile index within one variant, destination cell 0-29) pairs the game copies for part p."""
        size, pos = le16(self.data, PART_SIZE + 10 * t + 2 * p), le16(self.data, PART_POS + 10 * t + 2 * p)
        cols, rows, x, y = size // 10, size % 10, pos // 10, pos % 10
        out = []
        for r in range(rows - 1 if (t, p) == (0, 0) else rows):
            for c in range(cols):
                out.append((r * cols + c, (r + y) * FACE_W + x + c))
        if (t, p) == (0, 0):   # $C2:3ADA: the last row of the part is two loose tiles
            s = (rows - 1) * cols
            out += [(s, (y + 4) * FACE_W + x), (s + 4, (y + 4) * FACE_W + x + 4)]
        return out

    def part_variant(self, t: int, p: int, v: int) -> bytes:
        n = le16(self.data, PART_TILES + 10 * t + 2 * p) * 32
        base = self.part_base(t, p) + v * n
        return self.data[base:base + n]

    def face_tiles(self, code: int) -> bytes:
        """960 bytes of 4bpp tiles of a face code."""
        if not code & 0x8000:
            return self.entry(PORTRAIT_ENTRY + code)[:FACE_BYTES]
        d = [(code >> s) & 3 for s in (10, 8, 6, 4, 2, 0)]
        t = d[0]
        out = bytearray(FACE_BYTES)
        for p in PART_ORDER:
            src = self.part_variant(t, p, d[p + 1])
            for s, c in self.part_cells(t, p):
                out[32 * c:32 * c + 32] = src[32 * s:32 * s + 32]
        return bytes(out)

    def face_pixels(self, code: int) -> list[int]:
        tiles = self.face_tiles(code)
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, code: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(code)]

    # --- big map ---
    def map_tiles(self, region: int) -> bytes:
        return self.entry(MAP_ENTRY + region)

    def map_rgb(self, region: int) -> list[tuple[int, int, int]]:
        """MAP_W*8 x MAP_H*8 RGB of a region (land white, as before the owner colours)."""
        pal = [bgr555_rgb(le16(self.data, MAP_PALETTE + 2 * i)) for i in range(16)]
        ch = self.map_tiles(region)
        w = MAP_W * 8
        out = [(0, 0, 0)] * (w * MAP_H * 8)
        for t in range(MAP_W * MAP_H):
            ty, tx = divmod(t, MAP_W)
            for i, v in enumerate(decode_tile(ch[32 * t:32 * t + 32])):
                out[(ty * 8 + i // 8) * w + tx * 8 + i % 8] = pal[v]
        return out

    # --- battle maps ---
    def battle_map(self, m: int) -> dict:
        a = self.entry(BATTLE_A_ENTRY)[BATTLE_HEADER + BATTLE_MAP_BYTES * m:][:BATTLE_MAP_BYTES]
        b = self.entry(BATTLE_B_ENTRY)[BATTLE_MAP_BYTES * m:][:BATTLE_MAP_BYTES]
        cells = []
        for y in range(BATTLE_H):
            for x in range(BATTLE_W):
                c = 2 * (y * BATTLE_W + x)
                cells.append({"x": x, "y": y, "terrain": a[c] & 15, "flags": a[c] >> 4, "byte1": a[c + 1],
                              "overlay": le16(b, c)})
        return {"id": m, "a": a, "b": b, "cells": cells}

    @staticmethod
    def cell_tiles(cell: dict) -> list[int]:
        """The 4 tilemap tile numbers (TL TR BL BR, before the game's + 0x100) of a hex cell, as $C6:6AFF."""
        t, ov = cell["terrain"], cell["overlay"]
        if t in BATTLE_OVERLAY and ov != 0x8888:
            return [BATTLE_OVERLAY[t] + (ov >> 4 * k & 15) for k in range(4)]
        return [BATTLE_PLAIN + 4 * t + k for k in range(4)]

    @staticmethod
    def cell_pos(x: int, y: int) -> tuple[int, int]:
        """Top-left tile (column, row) of hex (x, y) in the 32 x 28 BG2 tilemap ($C6:2A94)."""
        return 2 * x + 2, 2 * y + 2 + (1 - x % 2)

    def battle_chars(self) -> bytes:
        return self.entry(BATTLE_TILE_ENTRY)

    def battle_rgb(self, m: int) -> tuple[int, int, list]:
        """(w, h, RGB list, None outside the hexes) of battle map m: the 28 x 25 tile area of the hexes."""
        ch = self.battle_chars()
        pal = [bgr555_rgb(le16(self.data, BATTLE_PALETTE + 2 * i)) for i in range(16)]
        w, h = 2 * BATTLE_W * 8, (2 * BATTLE_H + 1) * 8
        out: list = [None] * (w * h)
        for cell in self.battle_map(m)["cells"]:
            cx, cy = self.cell_pos(cell["x"], cell["y"])
            for k, t in enumerate(self.cell_tiles(cell)):
                n = t + 0x100 - BATTLE_TILE0
                tx, ty = cx - 2 + k % 2, cy - 2 + k // 2
                for i, v in enumerate(decode_tile(ch[32 * n:32 * n + 32])):
                    out[(ty * 8 + i // 8) * w + tx * 8 + i % 8] = pal[v]
        return w, h, out
