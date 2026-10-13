"""SFC 三國志英傑伝 (KOEI, 1995) ROM decoding.

Offsets are file offsets of the headerless 3 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
The LZ decompressor ($C0:F194) is the shared one in tools/koei_lz.py. Pointer tables are 4 bytes per entry
(long pointer + 00).
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Sangokushi Eiketsuden (Japan).zip")
LZ_TABLES = 0xF037                      # decompressor table block ($C0:F037), routine at $C0:F194

# Font: 1655 sorted LE16 Shift-JIS codes; glyph number = index in this table (binary search $C1:0878).
# Glyph g: 16x16 1bpp, 32 bytes at FONT + 32 g, 2 bytes per row (left half, right half), drawn by $C9:9371.
FONT_CODES = 0x9CA1D
GLYPH_COUNT = 1655
FONT = 0x220EC
# Game-specific characters in the user area 0xEB9F-0xEBE7 (identified from the glyphs and the names using
# them): data/ext_chars.txt. EBD5 is not identified.
EXT_CHARS_FILE = os.path.join(HERE, "data", "ext_chars.txt")


def _ext_chars() -> dict[int, str]:
    with open(EXT_CHARS_FILE, encoding="utf-8") as f:
        rows = [line.rstrip("\n").split("\t") for line in f if line.strip() and not line.startswith("#")]
    return {int(code, 16): ch for code, _, ch, *_ in rows}


EXT_CHARS = _ext_chars()

# Master table: 8 long pointers ($C8:EBA0). 0 = 73 raw bytes (unknown), 1-4 = place lists (LZ), 5 = NPC types
# (LZ), 6 = person names (LZ), 7 = person stats (LZ).
MASTER = 0x8EBA0
PERSON_COUNT = 384
NAME_SIZE, STATS_SIZE = 16, 19
PLACE_GROUPS, PLACE_COUNT, PLACE_SIZE = 4, 32, 21
NPC_COUNT, NPC_SIZE = 256, 9
PLACE_FILLER = "渡哲也"                # name of the unused place slots

# Name tables (4-byte pointers to NUL-terminated strings)
FORCE_NAMES, FORCE_COUNT = 0x37B5B, 15     # 劉備 ... 孔融, 無所属
CLASS_NAMES, CLASS_COUNT = 0x37BE6, 19     # 短兵 ... 輸送隊
# Three 19-byte tables indexed by class, read for the status screen; the first is 策略 at level 1 (短兵 20,
# 軽騎兵 15 on the screen), the other two presumably the 攻撃 / 防御 base (formula not solved)
CLASS_PARAMS = [0x37CAD, 0x37CC0, 0x37CD3]
TERRAIN_NAMES, TERRAIN_COUNT = 0x6E99A, 20  # 平地 ... 濁流

# Items: 183 x 20 bytes = name (13, NUL-padded), kind, price (FF = not sold), 5 unknown bytes
ITEMS, ITEM_COUNT, ITEM_SIZE = 0x7C987, 183, 20
ITEM_KINDS = {0: "斧・刀・鉤", 1: "指南書", 2: "策略書", 3: "消耗品", 4: "馬", 5: "甲・牌", 6: "槍・戟", 7: "弓",
              8: "弩", 9: "砲", 10: "圏・鉞・錘", 11: "鞭", 12: "笛・鼓", 13: "扇", 14: "車", 15: "宝剣"}

# Faces 0-239: 48x48 = 6x6 4bpp tiles row-major (1152 bytes), one LZ stream each; the face routine $C7:04F7
# picks the pointer table by code (< 72, < 144, < 216, < 240; other codes give face 0) and copies the tiles
# to $7E:8444. All faces use CGRAM palette 3 (FACE_PALETTE).
FACE_W, FACE_H = 6, 6
FACE_BYTES = 1152
FACE_COUNT = 240
FACE_TABLES = [(0, 0x11F7BC), (72, 0x12FB78), (144, 0x13FD1E), (216, 0x14492F)]
FACE_PALETTE = 0x4DE05

# Battles 0-57: battle n uses map stream n of BATTLE_MAPS ($C5:8DFD) and name n of BATTLE_NAMES + "の戦い"
# (before a trailing Ⅰ-Ⅲ).
# Map stream: W, H (16x16 blocks), W*H block numbers, (W/2)*(H/2) terrain bytes (32x32 cells, index of
# TERRAIN_NAMES). Block graphics set 1 for the maps listed in BATTLE_SET1 (19 LE16 at $C5:D4C5), else set 0:
# 4bpp tiles = stream [set] of BATTLE_GFX at VRAM tile BATTLE_TILE0, blocks = stream [2 + set] (256 blocks x
# 4 LE16 BG entries: top-left, top-right, bottom-left, bottom-right), palettes 4-6 = BATTLE_PALETTES[set].
BATTLE_COUNT = 58
BATTLE_MAPS = 0x1F45E
BATTLE_NAMES = 0x5D4EB
BATTLE_SUFFIX = 0x5D71D                 # "の戦い"
BATTLE_SET1, BATTLE_SET1_COUNT = 0x5D4C5, 19
BATTLE_GFX = 0x1CACD1
BATTLE_TILE0 = 64
BATTLE_PALETTES = [0x1CACF5, 0x1CAD55]  # 3 x 32 bytes each -> CGRAM palettes 4-6

# Big map (全体図): 4bpp tiles (LZ at WORLD_CHARS, VRAM tile 64), 32 x 28 LE16 BG tilemap (LZ at WORLD_TILEMAP),
# palettes 4-6 from WORLD_PALETTE. Place markers: BG entry WORLD_MARKER on another layer at tile (x, y) of
# WORLD_MARKER_XY; place list g (1-4) uses entries MARKER_START[g-1] + i, i < MARKER_COUNT[g-1], for its place i
# (FF FF = no marker). Chapter c ($7E:7618) shows place list CHAPTER_GROUP[c] + 1.
WORLD_CHARS = 0x1E0000
WORLD_TILEMAP = 0x1E35DE
WORLD_W, WORLD_H = 32, 28
WORLD_TILE0 = 64
WORLD_PALETTE = 0x4E653
WORLD_MARKER = 0x4E6B3
WORLD_MARKER_XY = 0x9C6EB
MARKER_COUNT = 0x9C5F7
MARKER_START = 0x9C5FC
CHAPTER_GROUP = 0x37B4A
CHAPTER_COUNT = 5


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


def text(raw: bytes) -> str:
    """Game string -> str: Shift-JIS (cp932) plus EXT_CHARS; stops at NUL. Unknown user-area codes -> [XXXX]."""
    out, i = [], 0
    while i < len(raw) and raw[i]:
        c = raw[i]
        if (0x81 <= c < 0xA0 or 0xE0 <= c < 0xFD) and i + 1 < len(raw):
            code = c << 8 | raw[i + 1]
            if code in EXT_CHARS:
                out.append(EXT_CHARS[code])
            elif code >= 0xEB9F:
                out.append(f"[{code:04X}]")
            else:
                out.append(bytes(raw[i:i + 2]).decode("cp932", "replace"))
            i += 2
        else:
            out.append(bytes([c]).decode("cp932", "replace"))
            i += 1
    return "".join(out)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        assert koei_lz.find_tables(self.data) == LZ_TABLES
        self._cache: dict[int, bytes] = {}

    # --- generic ---
    def ptr(self, table: int, i: int) -> int:
        """File offset of 4-byte pointer i of a pointer table."""
        return hirom(int.from_bytes(self.data[table + 4 * i:table + 4 * i + 3], "little"))

    def stream(self, p: int) -> bytes:
        """Decompressed LZ stream at file offset p."""
        if p not in self._cache:
            self._cache[p] = koei_lz.decompress(self.data, p, LZ_TABLES)[0]
        return self._cache[p]

    def string(self, p: int) -> str:
        return text(self.data[p:self.data.index(b"\0", p) + 1])

    def names(self, table: int, count: int) -> list[str]:
        return [self.string(self.ptr(table, i)) for i in range(count)]

    def glyph_codes(self) -> list[int]:
        return [le16(self.data, FONT_CODES + 2 * g) for g in range(GLYPH_COUNT)]

    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g."""
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[2 * y + x // 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    # --- master tables ---
    def forces(self) -> list[str]:
        return self.names(FORCE_NAMES, FORCE_COUNT)

    def classes(self) -> list[str]:
        return self.names(CLASS_NAMES, CLASS_COUNT)

    def class_params(self) -> list[list[int]]:
        """Per class: the bytes of the three CLASS_PARAMS tables."""
        return [[self.data[t + c] for t in CLASS_PARAMS] for c in range(CLASS_COUNT)]

    def terrains(self) -> list[str]:
        return self.names(TERRAIN_NAMES, TERRAIN_COUNT)

    def persons(self) -> list[dict]:
        """Name record (16 bytes): +0 name (6), +6 reading (8, half-width), +14 face, +15 unknown.
        Stats record (19 bytes): +0 bit 7 always set, bits 0-6 force; +1 武力 +2 統率 +3 知力; +4 unknown LE16;
        +6 unknown; +7 class (CLASS_NAMES); +8 unknown (level?); +9 0; +10..17 items (FF none); +18 0."""
        names, stats = self.stream(self.ptr(MASTER, 6)), self.stream(self.ptr(MASTER, 7))
        out = []
        for pid in range(PERSON_COUNT):
            n = names[NAME_SIZE * pid:NAME_SIZE * (pid + 1)]
            s = stats[STATS_SIZE * pid:STATS_SIZE * (pid + 1)]
            out.append({"id": pid, "name_raw": n, "stats_raw": s, "name": text(n[0:6]), "reading": text(n[6:14]),
                        "face": n[14], "unknown15": n[15], "flag": s[0] >> 7, "force": s[0] & 0x7F,
                        "武力": s[1], "統率": s[2], "知力": s[3], "unknown4": le16(s, 4), "unknown6": s[6],
                        "class": s[7], "unknown8": s[8], "unknown9": s[9],
                        "items": [i for i in s[10:18] if i != 0xFF], "unknown18": s[18]})
        return out

    def items(self) -> list[dict]:
        out = []
        for i in range(ITEM_COUNT):
            o = ITEMS + ITEM_SIZE * i
            r = self.data[o:o + ITEM_SIZE]
            out.append({"id": i, "raw": r, "name": text(r[0:13]), "kind": r[13], "price": r[14],
                        "unknown": r[15:20].hex(" ")})
        return out

    def places(self, group: int) -> list[dict]:
        """Place list group 1-4 (32 x 21 bytes: name 8, reading 12, kind), with its big-map marker (x, y)."""
        raw = self.stream(self.ptr(MASTER, group))
        start, count = self.data[MARKER_START + group - 1], self.data[MARKER_COUNT + group - 1]
        out = []
        for i in range(PLACE_COUNT):
            r = raw[PLACE_SIZE * i:PLACE_SIZE * (i + 1)]
            xy = None
            if i < count:
                x, y = self.data[WORLD_MARKER_XY + 2 * (start + i)], self.data[WORLD_MARKER_XY + 2 * (start + i) + 1]
                xy = None if (x, y) == (0xFF, 0xFF) else (x, y)
            out.append({"group": group, "id": i, "name": text(r[0:8]), "reading": text(r[8:20]), "kind": r[20],
                        "marker": xy})
        return out

    def chapter_groups(self) -> list[int]:
        """Place list (1-4) shown on the big map in chapter c = $7E:7618."""
        return [self.data[CHAPTER_GROUP + c] + 1 for c in range(CHAPTER_COUNT)]

    def npc_types(self) -> list[dict]:
        raw = self.stream(self.ptr(MASTER, 5))
        return [{"id": i, "name": text(raw[NPC_SIZE * i:NPC_SIZE * i + 8]), "unknown": raw[NPC_SIZE * i + 8]}
                for i in range(NPC_COUNT)]

    # --- faces ---
    def face_palette(self) -> list[int]:
        return [le16(self.data, FACE_PALETTE + 2 * i) for i in range(16)]

    def face_tiles(self, n: int) -> bytes:
        """1152 bytes of 4bpp tiles of face n, as $C7:04F7 picks them."""
        if not 0 <= n < FACE_COUNT:
            n = 0
        base, table = [t for t in FACE_TABLES if n >= t[0]][-1]
        return self.stream(self.ptr(table, n - base))[:FACE_BYTES]

    def face_pixels(self, n: int) -> list[int]:
        """48x48 colour numbers of face n, row-major."""
        tiles = self.face_tiles(n)
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(n)]

    # --- battle maps ---
    def battle_set1(self) -> list[int]:
        return [le16(self.data, BATTLE_SET1 + 2 * i) for i in range(BATTLE_SET1_COUNT)]

    def battle_set(self, n: int) -> int:
        return int(n in self.battle_set1())

    def battle_names(self) -> list[str]:
        return self.names(BATTLE_NAMES, BATTLE_COUNT)

    def battle_suffix(self) -> str:
        return self.string(BATTLE_SUFFIX)

    def battle_titles(self) -> list[str]:
        """Battle titles as the game shows them ($7E:D97F): name + "の戦い", the suffix put before a trailing
        Ⅰ-Ⅲ (宛Ⅰ -> 宛の戦いⅠ)."""
        out = []
        for name in self.battle_names():
            num = name[-1] if name[-1] in "ⅠⅡⅢ" else ""
            out.append(name[:len(name) - len(num)] + self.battle_suffix() + num)
        return out

    def battle_map(self, n: int) -> dict:
        """{w, h (blocks), blocks (h rows of w), terrain (h/2 rows of w/2), set}."""
        s = self.stream(self.ptr(BATTLE_MAPS, n))
        w, h = s[0], s[1]
        b, t = s[2:2 + w * h], s[2 + w * h:2 + w * h + (w // 2) * (h // 2)]
        return {"id": n, "w": w, "h": h, "set": self.battle_set(n),
                "blocks": [list(b[w * y:w * (y + 1)]) for y in range(h)],
                "terrain": [list(t[w // 2 * y:w // 2 * (y + 1)]) for y in range(h // 2)]}

    def battle_chars(self, bset: int) -> bytes:
        """4bpp tiles loaded at VRAM tile BATTLE_TILE0."""
        return self.stream(self.ptr(BATTLE_GFX, bset))

    def battle_blocks(self, bset: int) -> list[list[int]]:
        """256 blocks x 4 BG entries (top-left, top-right, bottom-left, bottom-right)."""
        raw = self.stream(self.ptr(BATTLE_GFX, 2 + bset))
        return [[le16(raw, 8 * b + 2 * q) for q in range(4)] for b in range(256)]

    def battle_palettes(self, bset: int) -> dict[int, list[int]]:
        base = BATTLE_PALETTES[bset]
        return {4 + k: [le16(self.data, base + 32 * k + 2 * i) for i in range(16)] for k in range(3)}

    def battle_tilemap(self, n: int) -> list[list[int]]:
        """(2h) rows of (2w) BG entries of battle map n."""
        m = self.battle_map(n)
        blocks = self.battle_blocks(m["set"])
        out = [[0] * (2 * m["w"]) for _ in range(2 * m["h"])]
        for by, row in enumerate(m["blocks"]):
            for bx, b in enumerate(row):
                for q, e in enumerate(blocks[b]):
                    out[2 * by + q // 2][2 * bx + q % 2] = e
        return out

    def _render(self, tilemap: list[list[int]], chars: bytes, tile0: int, pals: dict[int, list[int]]) -> list:
        h, w = len(tilemap) * 8, len(tilemap[0]) * 8
        rgb = {p: [bgr555_rgb(c) for c in v] for p, v in pals.items()}
        out: list = [(0, 0, 0)] * (w * h)
        cache: dict[int, list[int]] = {}
        for ty, row in enumerate(tilemap):
            for tx, e in enumerate(row):
                t, p = (e & 0x3FF) - tile0, e >> 10 & 7
                if not 0 <= t < len(chars) // 32 or p not in rgb:
                    continue
                if t not in cache:
                    cache[t] = decode_tile(chars[32 * t:32 * t + 32])
                for k, v in enumerate(cache[t]):
                    y, x = divmod(k, 8)
                    if e & 0x8000:
                        y = 7 - y
                    if e & 0x4000:
                        x = 7 - x
                    out[(ty * 8 + y) * w + tx * 8 + x] = rgb[p][v]
        return out

    def battle_rgb(self, n: int) -> list:
        """16 w x 16 h pixels of battle map n, row-major RGB."""
        bset = self.battle_set(n)
        return self._render(self.battle_tilemap(n), self.battle_chars(bset), BATTLE_TILE0, self.battle_palettes(bset))

    # --- big map ---
    def world_chars(self) -> bytes:
        return self.stream(WORLD_CHARS)

    def world_tilemap(self) -> list[list[int]]:
        raw = self.stream(WORLD_TILEMAP)
        return [[le16(raw, 2 * (y * WORLD_W + x)) for x in range(WORLD_W)] for y in range(WORLD_H)]

    def world_palettes(self) -> dict[int, list[int]]:
        return {4 + k: [le16(self.data, WORLD_PALETTE + 32 * k + 2 * i) for i in range(16)] for k in range(3)}

    def world_rgb(self) -> list:
        """256 x 224 RGB of the big map without markers."""
        return self._render(self.world_tilemap(), self.world_chars(), WORLD_TILE0, self.world_palettes())

    def world_marker(self) -> int:
        return le16(self.data, WORLD_MARKER)
