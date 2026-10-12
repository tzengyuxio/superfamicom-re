"""SFC スーパー三國志II (KOEI, 1991) ROM decoding.

Offsets are file offsets of the headerless 1 MB LoROM image. See san2/docs/ROM_FORMAT.md.
"""
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Super Sangokushi II (Japan).zip")
KANJI_EXT = os.path.join(HERE, "data", "kanji_ext.json")

FILE_TABLE = 0x7800           # bank 0 $F800: 16-byte entries (name[8], bank LE16, addr LE16, size LE32)

# sdata (scenario/master data), file offset 0xFBE0
PERSON_COUNT = 352
NAME_TABLE = 0x146C0          # 352 x 15: kanji codes (7, BE16 each, 00-terminated) + reading (8, half-width kana)
NAME_SIZE = 15
PERSON_TABLE = 0x12434        # 352 x 9: 義理 人德 野望 相性, 親族 LE16, 生年, 頭像 LE16
PERSON_SIZE = 9
ABILITY_TABLE = 0x13094       # 352 x 3: 才智 戰力 號召
SCENARIO_HEADER = 0xFBE4      # 6 x 20 bytes: year LE16 (game year - 1) + 18 unknown
SCENARIO_COUNT = 6
SCENARIO_YEARS = [189, 194, 201, 208, 215, 220]
LOYALTY = 0x11BF4             # 352 x 6: loyalty per scenario (FF = absent; rulers and free generals 00)
PLACEMENT = 0x1766C           # 352 x 22: debut year, ?, province x6, id LE16, list link/flags LE16 x6
PROVINCE_COUNT = 41
PROVINCES = 0xFD1E            # 6 x 41 x 25: +8 gold, food, population LE16, +14 faction, +20 土 民 水 馬 信
PROVINCE_SIZE = 25
ADJACENCY = 0x196A4           # 41 x 6, 1-based, FF = none; slot d and 5-d are opposite hex sides
CURSOR_GRID = 0x1166C         # 8 x 9 grid of 0-based provinces for the map cursor (FF = none)
HEX_DIRS = [(1, 0), (1, -1), (0, -1), (0, 1), (-1, 1), (-1, 0)]  # axial step of each adjacency slot

# Battle fields (file hpoint): 41 x 78 = 13 x 12 hexes, 4 bits each (high nibble first), row-major
BATTLE = 0x322D4
BATTLE_COLS, BATTLE_ROWS = 13, 12
TERRAIN = ["平地", "森", "林", "山", "河", "村", "城"]  # names from the FC version (same data)
TERRAIN_CELLS = 0x33370       # 7 x 4 BG tilemap entries LE16 (TL, TR, BL, BR) per terrain
BATTLE_GFX = 0xD31C0          # 4bpp tiles of VRAM tiles 0x1C0-: 平地..山 (16), then 村, 城 (8)
RIVER_GFX = 0xD34C0           # 河 (VRAM tiles 0x1D0-0x1D3) is animated: tile n, frame j (0-3) at + 32 (4n + j)
RIVER_FRAME = 0               # the frame on screen at the capture in tools/battle_capture.py
BATTLE_PALETTE = 0x144EC      # BG palettes 0-2 of the battle screen

# Big map: a 28 x 18 tile bitmap (VRAM tiles 0x1D0-, row-major), BG palette 7. The game paints the
# provinces' faction colours over colour 7 (white) at run time.
MAP_TILES = 0x88000
MAP_W, MAP_H = 28, 18
MAP_PALETTE = 0x1424C

# Faces: 40x48 = 5x6 4bpp tiles, row-major, 960 bytes
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_TILES = 0x90000      # banks $12-$18: 34 portraits per 32 KB bank, codes 1-208
PORTRAITS_PER_BANK = 34
PORTRAIT_COUNT = 208
PORTRAIT_PALETTE = 0x1DA81    # sdata: palette number (0-3) per portrait code
FACE_PALETTES = 0x140EC       # sdata: 4 x 16 BGR555, loaded into CGRAM palettes 8-11
COMPOSITE_TILES = 0xC8000     # bank $19: 8 heads x 4 records (base, A, B, C) x 960 bytes
COMPOSITE_HEADS = 8
HEAD_SIZE = 4 * FACE_BYTES
COMPOSITE_PARTS = 0xCDF2      # 8 heads x 6 bytes: eyes/nose/mouth start column, then their widths
PART_ROWS = {"eyes": 2, "nose": 3, "mouth": 4}
# Composite face code: bit 15 set, bits 0-2 head, then a record number (0-3) per area, bits 13-14 palette.
# "top"/"bottom" = the cells above/below the boundary row minus the part cells. Head 3's boundary is
# row 2, the others' row 3 (seen in the game's reads; no table found).
COMPOSITE_SLOTS = [("top", "上", 3), ("bottom", "下", 5), ("eyes", "眼", 7), ("nose", "鼻", 9), ("mouth", "口", 11)]
BOUNDARY_ROW = {3: 2}

# Kanji font: 16x16 1bpp, 32 bytes = 4 8x8 tiles (top-left, top-right, bottom-left, bottom-right), 8 bytes
# each (one per row, MSB left). The glyph of code X (0x8000-) is at FONT + (X - 0x8000) * 32.
FONT = 0x80000


def lorom(bank: int, addr: int) -> int:
    """CPU address (LoROM) -> file offset."""
    return (bank & 0x7F) * 0x8000 + (addr & 0x7FFF)


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc")))
            data = z.read(name)
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]  # drop a 512-byte copier header if present


def kana(raw: bytes) -> str:
    """Half-width katakana (cp932 0xA6-0xDF), 00-terminated or field-filling."""
    return raw.split(b"\0")[0].decode("cp932")


def is_composite(code: int) -> bool:
    return bool(code & 0x8000)


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


def load_kanji() -> dict[int, str]:
    with open(KANJI_EXT, encoding="utf-8") as f:
        return {int(k, 16): v for k, v in json.load(f).items()}


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)

    def files(self) -> list[dict]:
        out = []
        for o in range(FILE_TABLE, FILE_TABLE + 0x400, 16):
            e = self.data[o:o + 16]
            if not e[0]:
                break
            bank, addr = int.from_bytes(e[8:10], "little"), int.from_bytes(e[10:12], "little")
            out.append({"name": e[:8].split(b"\0")[0].decode("ascii"), "bank": bank, "addr": addr,
                        "offset": lorom(bank, addr), "size": int.from_bytes(e[12:16], "little")})
        return out

    def scenarios(self) -> list[dict]:
        out = []
        for s in range(SCENARIO_COUNT):
            o = SCENARIO_HEADER + 20 * s
            out.append({"year": int.from_bytes(self.data[o:o + 2], "little") + 1, "raw": self.data[o + 2:o + 20]})
        return out

    def persons(self) -> list[dict]:
        out = []
        for i in range(PERSON_COUNT):
            n = self.data[NAME_TABLE + NAME_SIZE * i:NAME_TABLE + NAME_SIZE * (i + 1)]
            codes = [n[k] << 8 | n[k + 1] for k in range(0, 6, 2) if n[k]]
            p = self.data[PERSON_TABLE + PERSON_SIZE * i:PERSON_TABLE + PERSON_SIZE * (i + 1)]
            a = self.data[ABILITY_TABLE + 3 * i:ABILITY_TABLE + 3 * (i + 1)]
            out.append({
                "id": i, "kanji_codes": codes, "reading": kana(n[7:15]),
                "int": a[0], "war": a[1], "charm": a[2],
                "duty": p[0], "virtue": p[1], "ambition": p[2], "compat": p[3],
                "kin": int.from_bytes(p[4:6], "little"), "born": p[6],
                "face": int.from_bytes(p[7:9], "little"),
                "offset": PERSON_TABLE + PERSON_SIZE * i,
            })
        return out

    def glyph(self, code: int) -> list[list[int]]:
        """16x16 bitmap (rows of 0/1) of a 2-byte kanji code."""
        g = self.data[FONT + (code - 0x8000) * 32:][:32]
        return [[g[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    # ------------------------------------------------------------------ scenarios
    def placement(self, n: int, sc: int) -> dict | None:
        """Where person n starts in scenario sc (None = not in the scenario)."""
        pl = PLACEMENT + 22 * n
        d = self.data
        assert d[pl + 8] | d[pl + 9] << 8 == n
        prov, loyalty, flags = d[pl + 2 + sc], d[LOYALTY + 6 * n + sc], d[pl + 11 + 2 * sc]
        if prov == 0xFF:
            return None
        appears = loyalty != 0xFF or d[pl] == SCENARIO_YEARS[sc] - 1  # the game starts in December of the year before
        status = "未登場" if not appears else "君主" if flags & 0x80 else "在野" if flags & 0x20 else "武將"
        soldiers = 0 if not appears or flags & 0x20 else 100 if flags & 0x80 else 50 if flags & 0x10 else 10
        return {"province": prov + 1, "status": status, "soldiers": soldiers,
                "loyalty": loyalty if status == "武將" and loyalty != 0xFF else None}

    def debut(self, n: int) -> int | None:
        v = self.data[PLACEMENT + 22 * n]
        return None if v == 0xFF else v

    def province(self, sc: int, i: int) -> dict:
        o = PROVINCES + PROVINCE_SIZE * (PROVINCE_COUNT * sc + i)
        r = self.data[o:o + PROVINCE_SIZE]
        return {"province": i + 1, "gold": r[8] | r[9] << 8, "food": r[10] | r[11] << 8,
                "population": r[12] | r[13] << 8, "faction": None if r[14] == 0xFF else r[14],
                "land": r[20], "loyalty": r[21], "flood": r[22], "horses": r[23], "trust": r[24]}

    def faction_rulers(self, sc: int) -> dict[int, int]:
        """Faction index -> ruler's person id: the ruler (flag 0x80) standing in a province of that faction."""
        out = {}
        for n in range(PERSON_COUNT):
            p = self.placement(n, sc)
            if p and p["status"] == "君主":
                out[self.province(sc, p["province"] - 1)["faction"]] = n
        return out

    def adjacency(self) -> list[list[int | None]]:
        """Per province, the neighbour (1-based) on each of the 6 hex sides (None = no neighbour)."""
        return [[None if v == 0xFF else v for v in self.data[ADJACENCY + 6 * i:ADJACENCY + 6 * i + 6]]
                for i in range(PROVINCE_COUNT)]

    def hex_layout(self) -> dict[int, tuple[int, int]]:
        """Axial hex coordinates of every province, following the sides of the adjacency table."""
        adj, pos, todo = self.adjacency(), {1: (0, 0)}, [1]
        while todo:
            i = todo.pop()
            for d, j in enumerate(adj[i - 1]):
                if j is None:
                    continue
                q = (pos[i][0] + HEX_DIRS[d][0], pos[i][1] + HEX_DIRS[d][1])
                if j in pos:
                    assert pos[j] == q, (i, j)
                else:
                    pos[j] = q
                    todo.append(j)
        assert len(pos) == PROVINCE_COUNT and len(set(pos.values())) == PROVINCE_COUNT
        return pos

    def battle_terrain(self, i: int) -> list[list[int]]:
        """13 x 12 terrain ids (rows of columns 0-12) of province i's battle field (0-based)."""
        d = self.data[BATTLE + 78 * i:BATTLE + 78 * i + 78]
        nib = [v for b in d for v in (b >> 4, b & 15)]
        return [nib[r * BATTLE_COLS:(r + 1) * BATTLE_COLS] for r in range(BATTLE_ROWS)]

    def palette(self, offset: int, count: int = 1) -> list[tuple[int, int, int]]:
        """count x 16 BGR555 colours at offset -> RGB."""
        d = self.data
        return [bgr555_rgb(d[offset + 2 * i] | d[offset + 2 * i + 1] << 8) for i in range(16 * count)]

    def map_pixels(self) -> list[tuple[int, int, int]]:
        """The big map (224 x 144) before the faction colours, RGB row-major."""
        pal, w = self.palette(MAP_PALETTE), MAP_W * 8
        out = [pal[0]] * (w * MAP_H * 8)
        for i in range(MAP_W * MAP_H):
            for k, v in enumerate(decode_tile(self.data[MAP_TILES + 32 * i:MAP_TILES + 32 * i + 32])):
                out[(i // MAP_W * 8 + k // 8) * w + i % MAP_W * 8 + k % 8] = pal[v]
        return out

    def terrain_cells(self) -> list[list[int]]:
        """Per terrain, its 4 BG tilemap entries (TL, TR, BL, BR)."""
        d = self.data
        return [[d[TERRAIN_CELLS + 8 * t + 2 * k] | d[TERRAIN_CELLS + 8 * t + 2 * k + 1] << 8 for k in range(4)]
                for t in range(len(TERRAIN))]

    def battle_tile(self, entry: int) -> list[int]:
        """Colour numbers (0-15) of the BG tile a battle tilemap entry points at."""
        n = (entry & 0x3FF) - 0x1C0
        if 0x10 <= n < 0x14:  # 河
            o = RIVER_GFX + 32 * (4 * (n - 0x10) + RIVER_FRAME)
        else:
            o = BATTLE_GFX + 32 * (n if n < 0x10 else n - 4)
        return decode_tile(self.data[o:o + 32])

    def battle_pixels(self, i: int) -> tuple[int, int, list[tuple[int, int, int]]]:
        """Province i's battle field as the game draws it (26 x 25 tiles, odd columns half a hex lower)."""
        pal, cells = self.palette(BATTLE_PALETTE, 3), self.terrain_cells()
        w, h = 16 * BATTLE_COLS, 8 * (2 * BATTLE_ROWS + 1)
        out = [pal[0]] * (w * h)
        for r, row in enumerate(self.battle_terrain(i)):
            for c, t in enumerate(row):
                for k, e in enumerate(cells[t]):
                    x0, y0 = 16 * c + 8 * (k % 2), 16 * r + 8 * (c % 2) + 8 * (k // 2)
                    for j, v in enumerate(self.battle_tile(e)):
                        out[(y0 + j // 8) * w + x0 + j % 8] = pal[(e >> 10 & 7) * 16 + v]
        return w, h, out

    # ------------------------------------------------------------------ faces

    def face_palettes(self) -> list[list[int]]:
        """The 4 face palettes as BGR555 values (16 each)."""
        d = self.data
        return [[int.from_bytes(d[FACE_PALETTES + 32 * p + 2 * i:FACE_PALETTES + 32 * p + 2 * i + 2], "little")
                 for i in range(16)] for p in range(4)]

    def portrait_offset(self, code: int) -> int:
        i = code - 1
        return PORTRAIT_TILES + (i // PORTRAITS_PER_BANK) * 0x8000 + (i % PORTRAITS_PER_BANK) * FACE_BYTES

    def composite_areas(self, head: int) -> dict[str, set[int]]:
        """Cell numbers (0-29) of each slot for a head."""
        p = self.data[COMPOSITE_PARTS + 6 * head:COMPOSITE_PARTS + 6 * head + 6]
        areas = {}
        for k, name in enumerate(("eyes", "nose", "mouth")):
            row = PART_ROWS[name]
            areas[name] = {row * FACE_W + p[k] + i for i in range(p[3 + k])}
        parts = areas["eyes"] | areas["nose"] | areas["mouth"]
        boundary = BOUNDARY_ROW.get(head, 3) * FACE_W
        areas["top"] = {c for c in range(boundary) if c not in parts}
        areas["bottom"] = {c for c in range(boundary, FACE_W * FACE_H) if c not in parts}
        return areas

    def face_cells(self, code: int) -> list[int]:
        """ROM offset of each of the 30 tiles of a face."""
        if not is_composite(code):
            base = self.portrait_offset(code)
            return [base + 32 * c for c in range(30)]
        head = code & 7
        cells = [0] * 30
        for sid, _, shift in COMPOSITE_SLOTS:
            record = COMPOSITE_TILES + head * HEAD_SIZE + (code >> shift & 3) * FACE_BYTES
            for c in self.composite_areas(head)[sid]:
                cells[c] = record + 32 * c
        return cells

    def face_palette_number(self, code: int) -> int:
        return code >> 13 & 3 if is_composite(code) else self.data[PORTRAIT_PALETTE + code]

    def face_pixels(self, code: int) -> bytes:
        """40x48 colour numbers (0-15) of a face, row-major."""
        tiles = [decode_tile(self.data[o:o + 32]) for o in self.face_cells(code)]
        return bytes(tiles[(y // 8) * FACE_W + x // 8][(y % 8) * 8 + x % 8]
                     for y in range(FACE_H * 8) for x in range(FACE_W * 8))
