"""SFC 大航海時代II (KOEI, 1993) ROM decoding.

Offsets are file offsets of the headerless 2 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
The LZ decompressor ($C0:A24C, dispatcher service 0x4C) is the shared one in tools/koei_lz.py.
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Daikoukai Jidai II (Japan).zip")
LZ_TABLES = 0xA0EF                      # decompressor table block ($C0:A0EF), routine at $C0:A24C

# Text: half-width kana (JIS X 0201) drawn as hiragana, ESC K (1B 4B) switches to katakana, ESC H (1B 48) back;
# 2-byte codes 0x8140-0x879E are font glyphs (data/charset.txt), 0x9140 + k stands for 0x8200 + 0x100 k (codes whose
# low byte would be 00, which ends a string). Font: 16x16 1bpp, glyph g = 32 bytes at FONT + 32 g, tiles TL TR BL BR.
FONT = 0x1F3000
TEXT_BASE, TEXT_END = 0x8140, 0x879F
TEXT_ESCAPE = 0x9140
CHARSET = os.path.join(HERE, "data", "charset.txt")

# Initial game state: ROM INIT (0x6EEF bytes) is copied to WRAM $7E:2000 at power-on (routine $7E:F589), before the
# title screen; every table below with a W address lives in it (WRAM address = ROM offset - 0x8580D).
INIT = 0x8780D
INIT_WRAM = 0x2000
INIT_SIZE = 0x6EEF


def wram(offset: int) -> int:
    """WRAM address ($7E:xxxx) of a ROM offset inside the initial game state block."""
    return offset - INIT + INIT_WRAM


# Persons 0-119 (W25FC): 50 bytes. 0-5 the playable heroes, 6-68 mates, 69-78 story characters, 79-119 rivals.
PERSONS = 0x87E09
PERSON_COUNT, PERSON_SIZE = 120, 50
STATS = ["統率力", "航海術", "知識", "直感", "勇気", "剣技", "魅力"]   # +28..+34, names as in the table at 0xB39E3
HEROES = 6
HERO_PORTS = 0x7F76C            # 6 bytes: home port of each hero, stored at $7E:2016 when the hero is chosen
# VIPs 0-19 (W3D6C): 22 bytes = name (13), 4 x 0, ?, kind (+17), face (+18), 0, ? (+20), port (+21)
VIPS = 0x89579
VIP_COUNT, VIP_SIZE = 20, 22
# Women 0-29 (W3F24): 19 bytes = name (13), age? (+13), port? (+14), 0, FF, FF, ? (+18)
WOMEN = 0x89731
WOMAN_COUNT, WOMAN_SIZE = 30, 19
# Fleets 0-70 (W4158): 133 bytes. Fleet 0 is the player's (filled in when the game starts); 1 + 10 k is the start
# fleet of the hero of country k (0-5), the rest are NPC fleets (10 per country, 61-70 pirates).
FLEETS = 0x89965
FLEET_COUNT, FLEET_SIZE = 71, 133
FLEET_SHIPS, FLEET_SHIP_SIZE = 10, 9    # 10 ships of 9 bytes from +9; first byte FF = no ship
# Ship types 0-24 (W6FBF): name (18), number, flags?, ?, LE16, LE16; specs (W7230) 12 bytes per type
SHIP_TYPES = 0x8C7CC
SHIP_TYPE_COUNT, SHIP_TYPE_SIZE = 25, 25
SHIP_SPECS = 0x8CA3D
SHIP_SPEC_SIZE = 12
# Ports 0-129 (W735C): x, y (LE16, map cells), name (17), flags (low nibble = country 0-5, 6 = none);
# 0-99 trade ports (state below), 100-129 supply ports
PORTS = 0x8CB69
PORT_COUNT, PORT_SIZE = 130, 22
TRADE_PORTS = 100
# Port state 0-99 (W7E87): 37 bytes
PORT_STATE = 0x8D694
PORT_STATE_SIZE = 37
# Items 0-99 (ROM only, $C8:E7DD): name (17), 0, icon?, price (LE16), power?, category (index in ITEM_CATEGORIES)
ITEMS = 0x8E7DD
ITEM_COUNT, ITEM_SIZE = 100, 23

# String tables: n 3-byte pointers immediately followed by the strings (n = (first pointer - table) / 3)
COUNTRIES = 0xB3964             # ポルトガル ... オランダ, 海賊
GOODS = 0xB3CDF                 # 46 goods
GOODS_CATEGORIES = 0xB37AB      # 香辛料 ... その他
CANNONS = 0xB3803               # 未搭載, カノン砲 ...
RANKS = 0xB3926                 # "", 提督 ... 航海士
SKILLS = 0xB39BB                # 測量 地図 砲術 会計 交渉
STAT_NAMES = 0xB39E3            # 統率力 ... 魅力
WOODS = 0xB3AD3                 # チーク ... 鉄張り
FIGUREHEADS = 0xB3B11           # "", 海獣 ... 女神
DISCOVERY_CATEGORIES = 0xB3B77  # 財宝 先住民 ...
ITEM_CATEGORIES = 0xB3BBB       # 剣 刺突剣 ... 秘宝
LIQUORS = 0xB3C35
PEERAGES = 0xB4520              # "", 士爵 ... 大宰相
NAME_POOL = 0xB4996             # 192 first / last names
DISCOVERY_NAMES = 0x5E3AA       # 100 discoveries
DISCOVERY_TEXTS = 0x5C2F4
ITEM_TEXTS = 0x5EA14            # 100 item descriptions
BUILDINGS = 0x5C217             # 交易所 酒場 ...

# Faces: 40x48 = 5x6 4bpp tiles row-major (960 bytes), drawn as OBJ (tiles 0x1C0 / 0x1E0, VRAM bytes 0x3800 / 0x3C00).
# Code bit 15 clear: portrait 0-127, LZ stream at PORTRAIT_BASE + 3-byte offset PORTRAIT_OFFSETS[n] ($C1:42BB);
# palette PORTRAIT_PALETTE. Bit 15 set: composed face ($C1:3B22), see Rom.face_tiles.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_COUNT = 128
PORTRAIT_OFFSETS = 0x4CFEA
PORTRAIT_BASE = 0x17C73A
PORTRAIT_PALETTE = 0xAAC06
PACK_OFFSETS = 0x4CDD1          # 7 x 3-byte offsets; pack = 8 faces x 30 tiles
PACK_BASE = 0x19F2D6
PACK_PALETTE = 0x1F36E          # + 32 for pack 2
PACK_COUNT = 7
# Tile offsets inside the 30-tile face per pack ($C1:F3AE, +0x0E, +0x1C): part A (code bits 3-5) writes n tiles at
# 15 + PART_A1[t] (n = 1 for packs 0, 1, 6, else 2) and m tiles at 20 + PART_A2[t] (m = 2 for pack 1, else 3);
# part B (bits 6-8) writes 3 tiles at 10 + PART_B[t]
PART_B = 0x1F3AE
PART_A1 = 0x1F3AE + 0x0E
PART_A2 = 0x1F3AE + 0x1C

# World map ($C4:7E3C): 90 x 45 blocks of 12 x 12 metatiles (2 x 2 cells of 8 x 8 px) = 2160 x 1080 cells. Block b:
# LZ stream at MAP_BASE + 3-byte offset MAP_OFFSETS[b] (144 bytes); metatile v >= 0x10 = 4 cell values at
# MAP_META + 4 v (TL TR BL BR), v < 0x10 = bits 8 4 2 1 (TL TR BL BR) set -> 0x80 (land) else 0 (sea).
MAP_BLOCKS_W, MAP_BLOCKS_H, MAP_BLOCK = 90, 45, 12
MAP_W, MAP_H = MAP_BLOCKS_W * 2 * MAP_BLOCK, MAP_BLOCKS_H * 2 * MAP_BLOCK
MAP_OFFSETS = 0x3CD9C
MAP_BASE = 0x10CB9F             # $D0:CB9F (long at $C3:CC74)
MAP_META = 0xE0000              # $CE:0000 (long at $C3:CC6C)
MAP_TILE_PALETTE = 0xE0400      # byte per tile: BG palette - 2 ($C6:041B)
MAP_BANDS = 0x6D142             # LE16 per block row ($C6:0115): band = v + 1 if v <= 4 else 9 - v
MAP_CHARS = 0x167276            # LZ, 256 4bpp tiles at VRAM word 0x2000
# Map palettes: BG palette 2 = MAP_PALETTE2 + 32 k (4 variants k that differ in colours 1-3, which cycle while time
# passes at sea); BG palettes 3-5 come from groups MAP_PALETTE_GROUPS + 0x100 g of 8 rows (the 4 variants k, each in
# two frames with colours 12 and 13 swapped). Around Lisbon the game uses groups 0, 3, 4 for palettes 3, 4, 5; how it
# picks the groups elsewhere is not decoded. MAP_PALETTES = variant 2, frame 0 of those (used by export.py).
MAP_PALETTE2 = 0xAAD66
MAP_PALETTE_GROUPS = 0xAADE6
MAP_GROUPS_LISBON = [0, 3, 4]
MAP_PALETTES = [MAP_PALETTE2 + 32 * 2] + [MAP_PALETTE_GROUPS + 0x100 * g + 0x80 for g in MAP_GROUPS_LISBON]


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
        return "".join(line.rstrip("\n") for line in f if not line.startswith("#"))


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


def le24(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8 | raw[i + 2] << 16


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    r, g, b = c & 31, c >> 5 & 31, c >> 10 & 31
    return r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2


def decode_tile(raw: bytes) -> list[int]:
    """64 colour numbers of a 4bpp SNES tile (32 bytes), row-major."""
    out = []
    for y in range(8):
        p0, p1, p2, p3 = raw[2 * y], raw[2 * y + 1], raw[16 + 2 * y], raw[17 + 2 * y]
        for x in range(8):
            b = 7 - x
            out.append((p0 >> b & 1) | (p1 >> b & 1) << 1 | (p2 >> b & 1) << 2 | (p3 >> b & 1) << 3)
    return out


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = load_rom_bytes(path)
        self.charset = load_charset()
        self._map = None

    # --- text ---------------------------------------------------------------------------------------------------
    def text(self, raw: bytes) -> str:
        """Game text -> str (stops at 00)."""
        out, kata, i = [], False, 0
        while i < len(raw) and raw[i]:
            c = raw[i]
            if c == 0x1B:  # an ESC H can fall just past the end of a fixed-size name field
                kata = i + 1 < len(raw) and raw[i + 1] == 0x4B
                i += 2
                continue
            if 0x81 <= c <= 0x9F and i + 1 < len(raw):
                code = c << 8 | raw[i + 1]
                if TEXT_ESCAPE <= code < TEXT_ESCAPE + 6:
                    code = 0x8200 + ((code - TEXT_ESCAPE) << 8)
                out.append(self.charset[code - TEXT_BASE] if TEXT_BASE <= code < TEXT_END else f"{{{code:04X}}}")
                i += 2
                continue
            if 0xA1 <= c <= 0xDF:
                ch = unicodedata.normalize("NFKC", bytes([c]).decode("cp932"))
                if c in (0xDE, 0xDF) and out:  # voiced marks combine with the previous kana
                    out[-1] = unicodedata.normalize("NFC", out[-1] + ("゙" if c == 0xDE else "゚"))
                    i += 1
                    continue
                if not kata and "ァ" <= ch <= "ヶ":
                    ch = chr(ord(ch) - 0x60)
                out.append(ch)
            elif c == 0x2D:
                out.append("ー")
            else:
                out.append(chr(c))
            i += 1
        return "".join(out)

    def string_table(self, at: int) -> list[str]:
        """Strings of a table of 3-byte pointers that is followed by its strings."""
        d = self.data
        n = ((le24(d, at) & 0x3FFFFF) - at) // 3
        return [self.text(d[le24(d, at + 3 * k) & 0x3FFFFF:][:200]) for k in range(n)]

    def records(self, at: int, count: int, size: int) -> list[bytes]:
        return [self.data[at + size * k:at + size * (k + 1)] for k in range(count)]

    # --- tables -------------------------------------------------------------------------------------------------
    def persons(self) -> list[dict]:
        out = []
        for k, r in enumerate(self.records(PERSONS, PERSON_COUNT, PERSON_SIZE)):
            first, last = self.text(r[:13]), self.text(r[13:26])
            out.append({
                "id": k, "name": f"{first}・{last}" if last else first, "first": first, "last": last,
                "face": le16(r, 26), "stats": list(r[28:35]), "unk35": r[35], "sail_level": r[36], "battle_level": r[37],
                "sail_exp": le16(r, 38), "battle_exp": le16(r, 40), "age": r[42], "unk43": r[43], "unk44": r[44],
                "port": r[45], "unk46": r[46], "unk47": le16(r, 47), "country": r[49] & 15, "flags49": r[49] >> 4,
                "raw": r,
            })
        return out

    def vips(self) -> list[dict]:
        return [{"id": k, "name": self.text(r[:13]), "kind": r[17], "face": r[18], "unk20": r[20], "port": r[21],
                 "raw": r} for k, r in enumerate(self.records(VIPS, VIP_COUNT, VIP_SIZE))]

    def women(self) -> list[dict]:
        return [{"id": k, "name": self.text(r[:13]), "age": r[13], "port": r[14], "unk18": r[18], "raw": r}
                for k, r in enumerate(self.records(WOMEN, WOMAN_COUNT, WOMAN_SIZE))]

    def fleets(self) -> list[dict]:
        out = []
        for k, r in enumerate(self.records(FLEETS, FLEET_COUNT, FLEET_SIZE)):
            ships = [r[9 + FLEET_SHIP_SIZE * i:9 + FLEET_SHIP_SIZE * (i + 1)] for i in range(FLEET_SHIPS)]
            out.append({"id": k, "unk2": r[2], "port": r[4], "index": r[5], "active": r[7], "admiral": r[8],
                        "ships": [s for s in ships if s[0] != 0xFF and s[2] != 0xFF],
                        "x": le16(r, 99), "y": le16(r, 101), "x2": le16(r, 103), "y2": le16(r, 105),
                        "w111": le16(r, 111), "w115": [le16(r, 115 + 2 * i) for i in range(4)], "raw": r})
        return out

    def ship_types(self) -> list[dict]:
        out = []
        for k, r in enumerate(self.records(SHIP_TYPES, SHIP_TYPE_COUNT, SHIP_TYPE_SIZE)):
            spec = self.data[SHIP_SPECS + SHIP_SPEC_SIZE * k:SHIP_SPECS + SHIP_SPEC_SIZE * (k + 1)]
            out.append({"id": k, "name": self.text(r[:18]), "number": r[18], "flags": r[19], "b20": r[20],
                        "w21": le16(r, 21), "w23": le16(r, 23), "spec": spec, "raw": r})
        return out

    def ports(self) -> list[dict]:
        out = []
        for k, r in enumerate(self.records(PORTS, PORT_COUNT, PORT_SIZE)):
            p = {"id": k, "name": self.text(r[4:21]), "x": le16(r, 0), "y": le16(r, 2), "country": r[21] & 15,
                 "flags": r[21] >> 4, "raw": r}
            if k < TRADE_PORTS:
                s = self.data[PORT_STATE + PORT_STATE_SIZE * k:PORT_STATE + PORT_STATE_SIZE * (k + 1)]
                p.update({"unk0": s[0], "economy": int.from_bytes(s[1:5], "little"),
                          "industry": int.from_bytes(s[5:9], "little"), "shares": list(s[9:15]),
                          "price_levels": [c - 0x2D for c in s[15:25]], "w25": le16(s, 25), "b27": s[27],
                          "b28": s[28], "region": s[29], "items": [i for i in s[30:34] if i != 0xFF],
                          "b34": s[34], "b35": s[35], "state": s})
            out.append(p)
        return out

    def items(self) -> list[dict]:
        texts = self.string_table(ITEM_TEXTS)
        return [{"id": k, "name": self.text(r[:17]), "icon": r[18], "price": le16(r, 19), "power": r[21],
                 "category": r[22], "text": texts[k], "raw": r}
                for k, r in enumerate(self.records(ITEMS, ITEM_COUNT, ITEM_SIZE))]

    def discoveries(self) -> list[dict]:
        names, texts = self.string_table(DISCOVERY_NAMES), self.string_table(DISCOVERY_TEXTS)
        return [{"id": k, "name": n, "text": t} for k, (n, t) in enumerate(zip(names, texts))]

    # --- faces --------------------------------------------------------------------------------------------------
    def lz(self, at: int) -> bytes:
        return koei_lz.decompress(self.data, at, LZ_TABLES)[0]

    def portrait_tiles(self, n: int) -> bytes:
        return self.lz(PORTRAIT_BASE + le24(self.data, PORTRAIT_OFFSETS + 3 * n))[:FACE_BYTES]

    def pack_tiles(self, t: int) -> bytes:
        """The 8 faces of composed-face pack t (8 x 960 bytes)."""
        return self.lz(PACK_BASE + le24(self.data, PACK_OFFSETS + 3 * t))[:8 * FACE_BYTES]

    @staticmethod
    def pack_of(code: int) -> int:
        t = code >> 12 & 7
        return 6 if t == 7 else t

    @staticmethod
    def face_parts(code: int) -> list[int]:
        """Composed face code -> [upper face, lower face, part A, part B] (face numbers 0-7 of the pack)."""
        return [code >> 9 & 7, code & 7, code >> 3 & 7, code >> 6 & 7]

    def part_cells(self, t: int) -> dict[str, list[int]]:
        """Tile cells (0-29, row-major) each part of pack t writes, in the order $C1:3B22 writes them."""
        d = self.data
        n = 1 if t < 2 or t > 5 else 2
        m = 2 if t == 1 else 3
        a1, a2, b = le16(d, PART_A1 + 2 * t), le16(d, PART_A2 + 2 * t), le16(d, PART_B + 2 * t)
        return {"upper": list(range(20)), "lower": list(range(20, 30)) + ([15] if t == 1 else []),
                "a": list(range(15 + a1, 15 + a1 + n)) + list(range(20 + a2, 20 + a2 + m)),
                "b": list(range(10 + b, 13 + b))}

    def face_tiles(self, code: int) -> bytes:
        """960 bytes of 4bpp tiles the game puts in VRAM for a face code."""
        if not code & 0x8000:
            return self.portrait_tiles(code)
        t = self.pack_of(code)
        pack = self.pack_tiles(t)
        buf = bytearray(FACE_BYTES)
        for (part, cells), face in zip(self.part_cells(t).items(), self.face_parts(code)):
            for c in cells:
                buf[32 * c:32 * c + 32] = pack[FACE_BYTES * face + 32 * c:FACE_BYTES * face + 32 * c + 32]
        return bytes(buf)

    def face_palette(self, code: int) -> bytes:
        if not code & 0x8000:
            return self.data[PORTRAIT_PALETTE:PORTRAIT_PALETTE + 32]
        at = PACK_PALETTE + 32 * (self.pack_of(code) == 2)
        return self.data[at:at + 32]

    def face_pixels(self, code: int) -> list[int]:
        """40 x 48 colour numbers (0-15), row-major."""
        tiles = self.face_tiles(code)
        out = [0] * (40 * 48)
        for c in range(30):
            px = decode_tile(tiles[32 * c:32 * c + 32])
            cx, cy = c % FACE_W * 8, c // FACE_W * 8
            for i, v in enumerate(px):
                out[(cy + i // 8) * 40 + cx + i % 8] = v
        return out

    def face_rgb(self, code: int) -> list[tuple[int, int, int]]:
        pal = self.face_palette(code)
        colors = [bgr555_rgb(le16(pal, 2 * i)) for i in range(16)]
        return [colors[v] for v in self.face_pixels(code)]

    # --- world map ----------------------------------------------------------------------------------------------
    def map_block(self, b: int) -> bytes:
        """144 metatile values of block b (row-major 12 x 12)."""
        return self.lz(MAP_BASE + le24(self.data, MAP_OFFSETS + 3 * b))[:MAP_BLOCK * MAP_BLOCK]

    def map_cells(self) -> bytes:
        """MAP_W x MAP_H cell values (0 = sea, 0x80 = plain land, other = tile number), row-major."""
        if self._map is None:
            d, cells = self.data, bytearray(MAP_W * MAP_H)
            for b in range(MAP_BLOCKS_W * MAP_BLOCKS_H):
                by, bx = divmod(b, MAP_BLOCKS_W)
                for i, v in enumerate(self.map_block(b)):
                    q = d[MAP_META + 4 * v:MAP_META + 4 * v + 4] if v >= 0x10 else \
                        bytes(0x80 if v & m else 0 for m in (8, 4, 2, 1))
                    y, x = by * 24 + i // 12 * 2, bx * 24 + i % 12 * 2
                    cells[y * MAP_W + x:y * MAP_W + x + 2] = q[:2]
                    cells[(y + 1) * MAP_W + x:(y + 1) * MAP_W + x + 2] = q[2:]
            self._map = bytes(cells)
        return self._map

    def map_band(self, y: int) -> int:
        v = le16(self.data, MAP_BANDS + 2 * (y // 24))
        return v + 1 if v <= 4 else 9 - v

    def map_tile(self, x: int, y: int) -> int:
        """BG tilemap word of cell (x, y) as $C6:002F / $C6:041B build it (x wraps around)."""
        cells = self.map_cells()

        def cell(cx: int, cy: int) -> int:
            return cells[cy * MAP_W + cx % MAP_W] if 0 <= cy < MAP_H else 0

        v, band = cell(x, y), self.map_band(y)
        if v & 0x7F:
            t = v
        elif v:
            t = 0x80 + band
        else:
            m = sum(bit for bit, (dx, dy) in ((1, (0, -1)), (2, (1, 0)), (4, (0, 1)), (8, (-1, 0)))
                    if cell(x + dx, y + dy) >= 0x80)
            t = band * 16 + m if m else 0x0F
        return t | (self.data[MAP_TILE_PALETTE + t] + 2) << 10

    def map_chars(self) -> bytes:
        return self.lz(MAP_CHARS)[:0x2000]

    def map_palettes(self) -> list[bytes]:
        return [self.data[a:a + 32] for a in MAP_PALETTES]
