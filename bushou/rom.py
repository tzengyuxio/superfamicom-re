"""SFC スーパー信長の野望・武将風雲録 (KOEI, 1992) ROM decoding.

Offsets are file offsets of the headerless 1 MB LoROM image (file offset = (bank & 0x7F) * 0x8000 + addr - 0x8000).
No compression. The data tables are the FC version's (famicom-re/bushou) with a few layout changes; see
bushou/docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Super Nobunaga no Yabou - Bushou Fuuunroku (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

FILE_TABLE = 0x7800             # 16-byte entries: name[8], bank LE16, addr LE16, size LE32 (as in san2)

# ---------------------------------------------------------------- text
# Text: 2-byte big-endian codes 0x8140-0x84A3 = font glyph code - 0x8140 (data/charset.txt), half-width
# katakana (cp932 0xA1-0xDF) one byte each, 00 ends. Glyph g: 16x16 1bpp, 32 bytes at FONT + 32 * (code - 0x8000)
# (top-left, top-right, bottom-left, bottom-right 8x8 tiles, MSB left).
FONT = 0x85800
TEXT_BASE = 0x8140
GLYPH_COUNT = 868
ZERO_ESCAPE = 0x85F0  # 85F0 / 85F1 / 85F2 stand for 8200 / 8300 / 8400 (verified in Mesen: 君, 瀬)
# Glyphs 0x849B-0x84A3 hold 1.5 kanji each so that 3- and 4-kanji surnames fit 2 or 3 glyphs (as in FC)
GAIJI = [((0x849B, 0x849C, 0x849D), "長宗我部"), ((0x849E, 0x849C, 0x849D), "香宗我部"),
         ((0x849F, 0x84A0), "鳥屋尾"), ((0x84A1, 0x84A2), "佐々木")]

# ---------------------------------------------------------------- scenarios
# File "basedata" (0xCA42): two scenario blocks of 0x1B88 bytes back to back. The game copies block + 4 ..
# block + 0x1B8C to WRAM $7E:DC04, so block offset k is $7E:DC00 + k and the pointers inside are WRAM addresses.
WRAM = 0xDC00
BLOCK_COPY = (4, 0x1B8C)        # copied range of a block
SCENARIOS = [  # name, block, name table, start generals, later-general list
    ("戦国の動乱", 0xCA42, 0x10580, 250, 0x15008),
    ("信長包囲網", 0xE5CA, 0x12578, 255, 0x153D0),
]
SCENARIO_COUNT = len(SCENARIOS)
HEADER = 5                      # block +5 scenario number, +6 year - 1476, +7 month
PROVINCE_COUNT = 48
PROVINCE_START, PROVINCE_SIZE = 0x008, 32
TEA_START, TEA_SIZE, TEA_COUNT = 0x608, 3, 48
DAIMYO_START, DAIMYO_SIZE, DAIMYO_SLOTS = 0x698, 32, 48
GENERAL_START, GENERAL_SIZE = 0xC98, 15
GENERAL_SLOTS = 254             # slots inside the copied range
NAME_SIZE = 20                  # name record: family (7), given (7), charm, ambition, ?, birth - 1476, face LE16
NAME_BASE = 0xCA42              # general +2 (name pointer) is an offset from the start of "basedata"
LATER_FIRST = 257               # name record of later-appearing general k = 257 + k (FC: 256 + k)
LATER_SIZE = 8
BASE_YEAR = 1476
PROVINCE_NAMES = 0x1432C        # 48 x 13 bytes: name (2 glyph codes + 0), ?, neighbours (FF end)

# ---------------------------------------------------------------- faces
# 40x48 = 5x6 4bpp tiles row-major (960 bytes), DMA'd straight from the ROM ($00 bank DMA, VRAM word 0x6400).
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_BANK = 0x16            # dedicated face f: bank 0x16 + f // 34, (f % 34) * 960
PORTRAITS_PER_BANK = 34
PORTRAIT_COUNT = 180
COMPOSITE_TILES = 0xA8000       # bank 0x15: head h page p at + (4h + p) * 960
COMPOSITE_HEADS = 8
# 8 heads x 22 bytes: LE32 (unknown), then LE16 top count, bottom start, bottom count, (first, count) of
# eyes, nose, mouth. Cells are 0-29 row-major; the game copies top, bottom, eyes, nose, mouth in that order.
COMPOSITE_AREAS = 0x1793C
COMPOSITE_SLOTS = [("top", "上", 3), ("bottom", "下", 5), ("eyes", "眼", 7), ("nose", "鼻", 9), ("mouth", "口", 11)]
FACE_PALETTE = 0x174DC          # BG palette 5 of the province screen (all faces)

# ---------------------------------------------------------------- big map
# BG palettes 0-7 of the map screens at 0x1743C (32 bytes each). The land is BG1: a 28 x 17 tile bitmap
# (tiles row-major from MAP_TILES, palette 7) at tile (2, 5); the game paints faction colours over colour 7.
# The frame and sea are BG2: MAP_BG_W x MAP_BG_H tilemap entries at MAP_BG (tile (1, 2)).
BG_PALETTES = 0x1743C
MAP_TILES = 0x84000
MAP_W, MAP_H = 28, 17
MAP_PALETTE = 7
MAP_BG = 0x15A6C
MAP_BG_W, MAP_BG_H = 30, 21
MAP_ORIGIN, MAP_BG_ORIGIN = (2, 5), (1, 2)

# ---------------------------------------------------------------- battle maps
FIELD_MAPS = 0x3746A            # 48 x 154 bytes, 14 x 11 cells (column-odd hex rows), province order
CASTLE_MAPS = 0x393B2           # 49 x 143 bytes, 13 x 11 cells
CASTLE_LAYER = 0x3B0BE          # second layer of the castle maps, same shape
FIELD_W, CASTLE_W, BATTLE_H = 14, 13, 11
FIELD_COUNT, CASTLE_COUNT = 48, 49
FIELD_TERRAIN = {7: "平地", 8: "丘陵", 9: "林", 0xB: "海・湖", 0xC: "山", 0xD: "川"}
# Battle screen (field): BG2 (mode 2, tilemap VRAM word 0x0C00) = base frame rows at bank 7 $DEC6 (32 words a row),
# a 30 x 4 status window at bank 7 $DB4E put at tile (1, 1), then per cell (c, r) a 2x2 metatile at tile
# (2 + 2c, 5 + 2r + (c & 1)). Metatile = 4 LE16 tilemap entries TL TR BL BR in bank 7.
BATTLE_BASE = 0x3DEC6
BATTLE_STATUS = 0x3DB4E
FIELD_METATILES = {7: 0xD20A, 8: 0xD212, 9: 0xD21A, 0xA: 0xD3EA, 0xC: 0xD232}
FIELD_SEA = (0xD22A, 0xD222)    # second one when the cell above is sea or it is the first row
FIELD_RIVER = (0xCDCA, 0xCDFA)  # second one when the cell above is sea / river or it is the first row
BATTLE_PALETTES = 0x3CEEA       # BG palettes 0-5 (CGRAM 0)
# Battle names in the battle module "hexmain" (p-code address = 0x6000 + offset in the file): 49 LE16 pointers
# to the field names (0-47 per province, 48 empty) and 49 to the castle names (0-47 per province, 48 安土城).
HEXMAIN, HEXMAIN_BASE = 0x3F7BE, 0x6000
FIELD_NAMES, CASTLE_NAMES, BATTLE_NAME_COUNT = 0x459CB, 0x45B54, 49
# CHR DMAs of the battle screen: (ROM offset, VRAM word, bytes)
BATTLE_CHR = [(0x5C120, 0x4000, 0x1120), (0x5E860, 0x4E00, 0x400), (0x5D240, 0x5000, 0xA80),
              (0x5BF80, 0x5600, 0x1A0), (0x58E40, 0x5800, 0xC00), (0x5DCC0, 0x6800, 0xBA0), (0x5B380, 0x7800, 0xDA0)]


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


def is_composite(code: int) -> bool:
    return bool(code & 0x8000)


def decode_face_code(code: int) -> tuple[int, list[int]]:
    """Composite face code -> (head, page per slot in COMPOSITE_SLOTS order)."""
    return code & 7, [code >> bit & 3 for _, _, bit in COMPOSITE_SLOTS]


def portrait_offset(f: int) -> int:
    return lorom(PORTRAIT_BANK + f // PORTRAITS_PER_BANK, 0x8000 + f % PORTRAITS_PER_BANK * FACE_BYTES)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.charset = load_charset()

    def u16(self, o: int) -> int:
        return le16(self.data, o)

    # ------------------------------------------------------------ files and text

    def files(self) -> list[dict]:
        out = []
        for o in range(FILE_TABLE, FILE_TABLE + 0x400, 16):
            e = self.data[o:o + 16]
            if not e[0]:
                break
            bank, addr = le16(e, 8), le16(e, 10)
            out.append({"name": e[:8].split(b"\0")[0].decode("ascii"), "bank": bank, "addr": addr,
                        "offset": lorom(bank, addr), "size": int.from_bytes(e[12:16], "little")})
        return out

    def codes(self, raw: bytes) -> list[int]:
        """Text bytes -> codes (2-byte glyph codes and 1-byte kana), up to 00."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            if (0x81 <= raw[i] < 0xA0 or raw[i] >= 0xE0) and i + 1 < len(raw):
                c = raw[i] << 8 | raw[i + 1]
                if ZERO_ESCAPE <= c < ZERO_ESCAPE + 3:  # a code whose low byte is 00 cannot be stored (00 ends text)
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
            for seq, s in GAIJI:
                if tuple(cs[i:i + len(seq)]) == seq:
                    out.append(s)
                    i += len(seq)
                    break
            else:
                c = cs[i]
                if c < 0x100:
                    out.append(bytes([c]).decode("cp932", "replace"))
                else:
                    out.append(self.charset[c - TEXT_BASE] if TEXT_BASE <= c < TEXT_BASE + GLYPH_COUNT else "〓")
                i += 1
        return "".join(out)

    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g (code 0x8140 + g)."""
        a = FONT + 32 * (TEXT_BASE + g - 0x8000)
        raw = self.data[a:a + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    # ------------------------------------------------------------ provinces

    def province_names(self) -> list[str]:
        return [self.text(self.data[PROVINCE_NAMES + 13 * i:PROVINCE_NAMES + 13 * i + 5])
                for i in range(PROVINCE_COUNT)]

    def province_neighbours(self, p: int) -> list[tuple[int, int]]:
        """(province, high 2 bits) per neighbour."""
        o = PROVINCE_NAMES + 13 * p + 6
        out = []
        for b in self.data[o:o + 7]:
            if b == 0xFF:
                break
            out.append((b & 0x3F, b >> 6))
        return out

    # ------------------------------------------------------------ scenarios

    def block(self, s: int) -> int:
        return SCENARIOS[s][1]

    def scenario_info(self, s: int) -> dict:
        b = self.block(s)
        return {"name": SCENARIOS[s][0], "number": self.data[b + HEADER], "year": BASE_YEAR + self.data[b + HEADER + 1],
                "month": self.data[b + HEADER + 2]}

    def general_index(self, ptr: int) -> int:
        return (ptr - WRAM - GENERAL_START) // GENERAL_SIZE

    def name_record(self, s: int, i: int) -> dict:
        o = SCENARIOS[s][2] + NAME_SIZE * i
        r = self.data[o:o + NAME_SIZE]
        return {"family": self.text(r[:7]), "given": self.text(r[7:14]),
                "name": self.text(r[:7]) + self.text(r[7:14]), "charm": r[14], "ambition": r[15], "name_b16": r[16],
                "birth": BASE_YEAR + r[17], "face_code": le16(r, 18), "name_offset": o}

    def general_record(self, s: int, i: int) -> bytes:
        o = self.block(s) + GENERAL_START + GENERAL_SIZE * i
        return self.data[o:o + GENERAL_SIZE]

    def generals(self, s: int) -> list[dict]:
        """Generals present at the start of scenario s (slot i, name record i)."""
        info = self.scenario_info(s)
        out = []
        for i in range(SCENARIOS[s][3]):
            r = self.general_record(s, i)
            name_off = NAME_BASE + le16(r, 2)
            assert name_off == SCENARIOS[s][2] + NAME_SIZE * i, (s, i)
            nm = self.name_record(s, i)
            out.append({"index": i, **nm, "age": info["year"] - nm["birth"], "politics": r[4], "war": r[5],
                        "culture": r[6], "flags": r[7], "b8": r[8], "province": r[9], "daimyo": r[10],
                        "loyalty": r[11], "next": le16(r, 0)})
        return out

    def later_generals(self, s: int) -> list[dict]:
        """Generals that appear during scenario s (name record 257 + k)."""
        o, out = SCENARIOS[s][4], []
        while self.data[o] != 0:
            r = self.data[o:o + LATER_SIZE]
            k = len(out)
            nm = self.name_record(s, LATER_FIRST + k)
            out.append({"index": LATER_FIRST + k, **nm, "appear": BASE_YEAR + r[0],
                        "province": None if r[1] == 0xFF else r[1], "b2": r[2], "politics": r[3], "war": r[4],
                        "culture": r[5], "flags": r[6], "b7": r[7]})
            o += LATER_SIZE
        return out

    def renamed(self, s: int) -> list[dict]:
        """Name records between the start generals and 256 that hold later names (徳川家康, 豊臣秀吉)."""
        out = []
        for i in range(SCENARIOS[s][3], LATER_FIRST):
            nm = self.name_record(s, i)
            if nm["name"]:
                out.append({"index": i, **nm})
        return out

    def province_record(self, s: int, p: int) -> bytes:
        o = self.block(s) + PROVINCE_START + PROVINCE_SIZE * p
        return self.data[o:o + PROVINCE_SIZE]

    def provinces(self, s: int) -> list[dict]:
        names = self.province_names()
        out = []
        for p in range(PROVINCE_COUNT):
            r = self.province_record(s, p)

            def w(i, r=r):
                return le16(r, i)
            owner = (w(22) - WRAM - DAIMYO_START) // DAIMYO_SIZE if w(22) else None
            members, ptr = [], w(0)
            while ptr:
                g = self.general_index(ptr)
                members.append(g)
                ptr = le16(self.general_record(s, g), 0)
            out.append({"index": p, "name": names[p], "owner": owner, "gold": w(4), "rice": w(6), "kokudaka": w(8),
                        "flood": r[10], "town": w(11), "culture": r[13], "tech": w(14), "people_loyalty": r[16],
                        "castle": w(17), "soldiers": w(24), "guns": w(26), "training": r[28], "soldier_loyalty": r[29],
                        "generals": members, "ptr2": w(2), "raw19_21": r[19:22].hex(" "), "raw30_31": r[30:32].hex(" ")})
        return out

    def daimyos(self, s: int) -> list[dict]:
        out = []
        for d in range(DAIMYO_SLOTS):
            o = self.block(s) + DAIMYO_START + DAIMYO_SIZE * d
            r = self.data[o:o + DAIMYO_SIZE]
            if not le16(r, 0):
                continue
            g = self.general_index(le16(r, 0))
            rel = [(r[5 + k // 2] >> (4 * (1 - k % 2))) & 15 for k in range(DAIMYO_SLOTS)]
            out.append({"index": d, "general": g, "name": self.name_record(s, g)["name"],
                        "b2_4": [x for x in r[2:5] if x != 0xFF], "relations": rel, "b29": r[29], "b30": r[30],
                        "b31": r[31]})
        return out

    def tea(self, s: int) -> list[dict]:
        names_at = SCENARIOS[s][2] + NAME_SIZE * (LATER_FIRST + len(self.later_generals(s))) + NAME_SIZE
        out = []
        for t in range(TEA_COUNT):
            o = self.block(s) + TEA_START + TEA_SIZE * t
            ptr = self.u16(o)
            out.append({"index": t, "name": self.text(self.data[names_at + 13 * t:names_at + 13 * t + 13]),
                        "owner": self.general_index(ptr) if ptr else None, "value": self.data[o + 2]})
        return out

    # ------------------------------------------------------------ faces

    def palette(self, n: int) -> list[int]:
        """BG palette n of the map / province screens (BGR555 x 16)."""
        return [self.u16(BG_PALETTES + 32 * n + 2 * i) for i in range(16)]

    def face_palette(self) -> list[int]:
        return [self.u16(FACE_PALETTE + 2 * i) for i in range(16)]

    def portrait_tiles(self, f: int) -> bytes:
        o = portrait_offset(f)
        return self.data[o:o + FACE_BYTES]

    def composite_page(self, head: int, page: int) -> bytes:
        o = COMPOSITE_TILES + (4 * head + page) * FACE_BYTES
        return self.data[o:o + FACE_BYTES]

    def composite_table(self, head: int) -> list[int]:
        o = COMPOSITE_AREAS + 22 * head
        return [int.from_bytes(self.data[o:o + 4], "little")] + [self.u16(o + 4 + 2 * k) for k in range(9)]

    def composite_runs(self, head: int) -> dict[str, list[int]]:
        """Cells each slot copies, in the game's order (later slots overwrite earlier ones)."""
        t = self.composite_table(head)
        runs = {"top": list(range(t[1])), "bottom": list(range(t[2], t[2] + t[3]))}
        for k, sid in enumerate(["eyes", "nose", "mouth"]):
            runs[sid] = list(range(t[4 + 2 * k], t[4 + 2 * k] + t[5 + 2 * k]))
        return runs

    def composite_areas(self, head: int) -> dict[str, list[int]]:
        """Cells each slot ends up showing (top/bottom minus the eyes, nose and mouth cells)."""
        runs = self.composite_runs(head)
        parts = set(runs["eyes"] + runs["nose"] + runs["mouth"])
        out = {sid: [c for c in runs[sid] if c not in parts] for sid in ("top", "bottom")}
        out["top"] = [c for c in out["top"] if c not in runs["bottom"]]
        return {**out, **{sid: runs[sid] for sid in ("eyes", "nose", "mouth")}}

    def face_tiles(self, code: int) -> bytes:
        if not is_composite(code):
            return self.portrait_tiles(code)
        head, pages = decode_face_code(code)
        out = bytearray(FACE_BYTES)
        for (sid, _, _), page in zip(COMPOSITE_SLOTS, pages):
            src = self.composite_page(head, page)
            for c in self.composite_runs(head)[sid]:
                out[32 * c:32 * c + 32] = src[32 * c:32 * c + 32]
        return bytes(out)

    def face_pixels(self, code: int) -> list[int]:
        """40x48 colour numbers, row-major."""
        tiles = self.face_tiles(code)
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, code: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(code)]

    # ------------------------------------------------------------ big map

    def map_bg_entries(self) -> list[int]:
        return [self.u16(MAP_BG + 2 * i) for i in range(MAP_BG_W * MAP_BG_H)]

    def map_bg_tile(self, n: int) -> bytes:
        """4bpp tile n of BG2 on the map screen (VRAM word 0x4000 + 16 n): tiles below 0x200 come from
        0x84000, the rest from 0x90000 (DMA'd there by the map screen)."""
        o = MAP_TILES + 32 * n if n < 0x200 else 0x90000 + 32 * (n - 0x200)
        return self.data[o:o + 32]

    def map_land_pixels(self) -> list[int]:
        """BG1 land bitmap: MAP_W*8 x MAP_H*8 colour numbers of palette 7."""
        w = MAP_W * 8
        out = [0] * (w * MAP_H * 8)
        for t in range(MAP_W * MAP_H):
            px = decode_tile(self.data[MAP_TILES + 32 * t:MAP_TILES + 32 * t + 32])
            for i, v in enumerate(px):
                out[(t // MAP_W * 8 + i // 8) * w + t % MAP_W * 8 + i % 8] = v
        return out

    def map_rgb(self) -> tuple[int, int, list[tuple[int, int, int]]]:
        """(w, h, RGB) of the map window: BG2 frame and sea, BG1 land on top (colour 0 transparent)."""
        w, h = MAP_BG_W * 8, MAP_BG_H * 8
        pals = [[bgr555_rgb(c) for c in self.palette(n)] for n in range(8)]
        out = [pals[0][0]] * (w * h)
        for i, e in enumerate(self.map_bg_entries()):
            px = decode_tile(self.map_bg_tile(e & 0x3FF))
            pal = pals[e >> 10 & 7]
            ty, tx = divmod(i, MAP_BG_W)
            for k, v in enumerate(px):
                y, x = divmod(k, 8)
                if e & 0x8000:
                    y = 7 - y
                if e & 0x4000:
                    x = 7 - x
                if v:
                    out[(ty * 8 + y) * w + tx * 8 + x] = pal[v]
        dx, dy = (MAP_ORIGIN[0] - MAP_BG_ORIGIN[0]) * 8, (MAP_ORIGIN[1] - MAP_BG_ORIGIN[1]) * 8
        land = self.map_land_pixels()
        lw = MAP_W * 8
        for i, v in enumerate(land):
            if v:
                y, x = divmod(i, lw)
                out[(dy + y) * w + dx + x] = pals[MAP_PALETTE][v]
        return w, h, out

    # ------------------------------------------------------------ battle maps

    def battle_terrain(self, castle: bool, n: int) -> bytes:
        w, base = (CASTLE_W, CASTLE_MAPS) if castle else (FIELD_W, FIELD_MAPS)
        return self.data[base + n * w * BATTLE_H:base + (n + 1) * w * BATTLE_H]

    def castle_layer(self, n: int) -> bytes:
        return self.data[CASTLE_LAYER + n * CASTLE_W * BATTLE_H:CASTLE_LAYER + (n + 1) * CASTLE_W * BATTLE_H]

    def battle_names(self) -> tuple[list[str], list[str]]:
        """(field names, castle names), 49 each."""
        out = []
        for table in (FIELD_NAMES, CASTLE_NAMES):
            names = []
            for k in range(BATTLE_NAME_COUNT):
                o = HEXMAIN + self.u16(table + 2 * k) - HEXMAIN_BASE
                names.append(self.text(self.data[o:o + 16]))
            out.append(names)
        return out[0], out[1]

    # ------------------------------------------------------------ battle screen
    # (checked for all 48 field maps against the game's own BG2 tilemap, verify_maps.py)

    def battle_cell_metatile(self, terrain: bytes, i: int, width: int = FIELD_W) -> int:
        """Bank-7 address of the 2x2 metatile the game draws for cell i of a field map."""
        t = terrain[i] & 0x3F
        above = terrain[i - width] & 0x3F if i >= width else None
        if t == 0xB:
            return FIELD_SEA[1] if above in (None, 0xB) else FIELD_SEA[0]
        if t == 0xD:
            return FIELD_RIVER[1] if above in (None, 0xB, 0xD) else FIELD_RIVER[0]
        return FIELD_METATILES[t]

    def metatile(self, addr: int) -> list[int]:
        o = lorom(7, addr)
        return [self.u16(o + 2 * k) for k in range(4)]

    def battle_tilemap(self, terrain: bytes, width: int = FIELD_W) -> list[int]:
        """32 x 28 BG2 tilemap entries of the battle screen: base frame, status window, then the cells."""
        tm = [self.u16(BATTLE_BASE + 2 * k) for k in range(32 * 28)]
        for row in range(4):
            for k in range(30):
                tm[(1 + row) * 32 + 1 + k] = self.u16(BATTLE_STATUS + 60 * row + 2 * k)
        for i in range(len(terrain)):
            r, c = divmod(i, width)
            x, y = 2 + 2 * c, 5 + 2 * r + (c & 1)
            for k, e in enumerate(self.metatile(self.battle_cell_metatile(terrain, i, width))):
                tm[(y + k // 2) * 32 + x + k % 2] = e
        return tm

    def battle_bg_tile(self, n: int) -> bytes:
        """4bpp BG2 tile n of the battle screen (VRAM word 0x4000 + 16 n), from the battle screen's CHR DMAs."""
        word = 0x4000 + 16 * n
        for src, dest, size in BATTLE_CHR:
            if dest <= word < dest + size // 2:
                o = src + 2 * (word - dest)
                return self.data[o:o + 32]
        return bytes(32)

    def battle_rgb(self, terrain: bytes, width: int = FIELD_W) -> tuple[int, int, list[tuple[int, int, int]]]:
        """(w, h, RGB) of the battle screen's BG2 for a field map."""
        pals = [[bgr555_rgb(self.u16(BATTLE_PALETTES + 32 * p + 2 * k)) for k in range(16)] for p in range(6)]
        w, h = 256, 224
        out = [pals[0][0]] * (w * h)
        for i, e in enumerate(self.battle_tilemap(terrain, width)):
            px = decode_tile(self.battle_bg_tile(e & 0x3FF))
            pal = pals[min(e >> 10 & 7, 5)]
            ty, tx = divmod(i, 32)
            for k, v in enumerate(px):
                y, x = divmod(k, 8)
                y, x = (7 - y if e & 0x8000 else y), (7 - x if e & 0x4000 else x)
                if v:
                    out[(ty * 8 + y) * w + tx * 8 + x] = pal[v]
        return w, h, out
