"""SFC 信長の野望・天翔記 (KOEI, 1996) ROM decoding.

Offsets are file offsets of the headerless 3 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Nobunaga no Yabou - Tenshouki (Japan).zip")

# Compressed data: 659 long pointers ($C0-$EF bank) to streams for the decompressor at $C0:F194
DATA_TABLE = 0x1F95A4
DATA_COUNT = 659
# Tables of the decompressor (bank $C0)
LEN_VALUE, LEN_BITS, LEN_SHIFT = 0xF037, 0xF077, 0xF0B6
NEAR_OFFSET, NEAR_BITS = 0xF0BE, 0xF17E
FAR_SHIFT, FAR_BITS = 0xF187, 0xF18C

SCENARIO_COUNT = 2
SCENARIO_YEARS = [1547, 1571]  # 信長初陣, 信長包囲網

# Persons (ids 0-699)
PERSON_COUNT = 700
# Names per scenario (scenario s at id + 700 s): flag, surname SJIS (6) + 0, given name SJIS (6) + 0,
# 生年 - 1440, 3 unknown bytes
NAME_TABLE = 0xE1DF8
NAME_SIZE = 19
# 700 x 14: face code LE16, 政治 戦闘 智謀 上限 / 2, 魅力, 野望, 生年 - 1454, father's face code LE16
# (FFFF = none), 2 unknown bytes, 12-bit flags LE16
PERSON_TABLE = 0xD0F80
PERSON_SIZE = 14
BIRTH_BASE = 1454
# Scenario persons (data entries 9, 10): 700 x 35 bytes, see Rom.scenario_persons
SCENARIO_PERSONS = 9
SCENARIO_PERSON_SIZE = 35
APTITUDE = "EDCBAS"            # 3-bit aptitude grades (0 = E)
UNITS = ["足軽", "騎馬", "鉄砲", "水軍"]
RANKS = ["", "大名", "宿老", "家老", "部将", "侍大将", "足軽頭"]  # +33 bits 3-5 (0 = not in service)
STATUS = ["大名", "軍団長", "武将", "隠居?", "浪人", "姫", "未登場"]  # +33 bits 0-2 (3: only 浅井久政 in 1571)
TROOPS = ["足軽隊", "騎馬隊", "鉄砲隊"]

# Castles: 128 per scenario. Names: 2 x 128 x 11 (name SJIS 9 + 2 unknown bytes), uncompressed;
# records (data entries 7, 8): 128 x 23, see Rom.castles
CASTLE_COUNT = 128
CASTLE_NAMES = 0xD0480
CASTLE_NAME_SIZE = 11
SCENARIO_CASTLES = 7
CASTLE_SIZE = 23
# Name suffix ($C4:20CB): 城 except these 1-based castle numbers. 石山, 室町御所, 観音寺 and 稲葉山 change
# with events (石山本願寺 / 石山城, 二条城, 安土城, 岐阜城); the scenario-start form is used here.
CASTLE_SUFFIX = {10: "館", 42: "館", 7: "", 86: "", 60: "本願寺", 128: ""}
# Castle map data, 128 x 9 bytes (one table for both scenarios): +0 国, +7 x, +8 y (map tiles, the
# top-right tile of the castle drawn in the terrain); other bytes unknown
CASTLE_INFO = 0xD0000
CASTLE_INFO_SIZE = 9

# Big map: two 150 x 65 BG tilemaps (LE16 entries), uncompressed: terrain, then roads (drawn over it,
# colour 0 transparent). Tile n is data entry 19 tile n - 435 (VRAM tiles 435-735); CGRAM palettes 3-5.
MAP_TILEMAP = 0x22339D
MAP_W, MAP_H = 150, 65
MAP_TILES_ENTRY = 19
MAP_TILE0 = 435
MAP_PALETTES = 0x1F9E1D        # CGRAM palettes 3, 4, 5

# Field-battle maps: Japan cut into a 30 x 11 grid of maps (row-major), numbered 0-329, each 16 x 12 BG tiles
# (8 x 6 cells of 2 x 2 tiles). A battle shows the 3 x 4 maps around the castle. They are entries of a second
# pointer table, FIELD_TABLE: entry n (768 bytes) holds the terrain tilemap (192 LE16) and an overlay tilemap
# (192 LE16, 0 / FFFF = empty) for BG1 / BG2; entry 330 + n is its 8 x 6 terrain cells (11 = sea).
# Tilemap entry t is shown as t + 0x0D20: tile t + 0x120 (FIELD_TILES_ENTRY of TILE_TABLE) with
# palette 3 + (t >> 10 & 7) (FIELD_PALETTES, CGRAM 3-6).
FIELD_TABLE = 0x10DEA0
FIELD_COUNT = 330
FIELD_COLS, FIELD_ROWS = 30, 11
FIELD_MAP_W, FIELD_MAP_H = 16, 12
FIELD_CELLS = 330
FIELD_SHOWN = 0x0D20
TILE_TABLE = 0x1FB205
FIELD_TILES_ENTRY = 51
FIELD_TILE0 = 0x120
FIELD_PALETTES = 0x1FB56A      # CGRAM palettes 3-6

# 軍団 (data entries 13, 14): 128 x 31, see Rom.corps
SCENARIO_CORPS = 13
CORPS_SIZE = 31

# Faces: 40x48 = 5x6 4bpp tiles, row-major, 960 bytes. A face code with bit 15 clear is a portrait
# (data entry 347 + code, codes 0-311); with bit 15 set it is composed from a pack of 4 generic faces
# (entry 328 + pack): bits 0-4 pack, 5-6 top rows, 7-8 bottom rows, 9-10 eyes, 11-12 mouth.
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
PORTRAIT_ENTRY = 347
PORTRAIT_COUNT = 312
PACK_ENTRY = 328
PACK_COUNT = 19
PACK_ROWS = 0x3F1CC            # 19 x 3: top tile rows, eyes column, mouth column
PACK_MOUTH_TILES = 0x3F205     # 19: mouth width in tiles
PACK_PALETTE = 0x3F218         # 19 x LE16: palette number
PORTRAIT_PALETTE = 0x19205     # LE16 per portrait code: palette number
FACE_PALETTES = 0x1FA1DD       # 3 x 16 BGR555 (CGRAM palette 9 on the general's screen)
FACE_PALETTE_COUNT = 3
CREST_ENTRY = 327              # 家紋 tiles


def hirom(addr: int) -> int:
    """CPU address (HiROM, banks $C0-$FF) -> file offset."""
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


# User-defined SJIS codes: 3 glyphs that together draw a 4-kanji surname (EC8C seen on the daimyo list as 長宗;
# EC8F, used only by 親泰, read as 香宗)
GAIJI = {b"\xec\x8c\xec\x8d\xec\x8e": "長宗我部", b"\xec\x8f\xec\x8d\xec\x8e": "香宗我部"}


def sjis(raw: bytes) -> str:
    raw = raw.split(b"\0")[0]
    for code, text in GAIJI.items():
        raw = raw.replace(code, text.encode("shift_jis"))
    return raw.decode("shift_jis", "replace")


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc")))
            data = z.read(name)
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]  # drop a 512-byte copier header if present


def decompress(rom: bytes, p: int, limit: int = 1 << 20) -> tuple[bytes, int]:
    """The game's decompressor ($C0:F194), step by step: (output, end offset of the stream).

    A 16-bit bit window W is filled from little-endian words of the stream; flag bytes and literals
    are read from the same pointer in between. Flag bits (MSB first): 1 = literal byte; 0 = copy
    length + 1 bytes from distance + 1 back, with a prefix-coded length and distance taken from W.
    The length value 0xFF ends the stream.
    """
    w = n = avail = 0

    def take(bits: int) -> None:  # $C0:1794: shift `bits` new bits into W
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
        self._cache: dict[int | tuple[int, int], bytes] = {}

    def entry_offset(self, i: int) -> int:
        return hirom(int.from_bytes(self.data[DATA_TABLE + 3 * i:DATA_TABLE + 3 * i + 3], "little"))

    def entry(self, i: int) -> bytes:
        """Decompressed data entry i of DATA_TABLE."""
        return self.table_entry(DATA_TABLE, i)

    def table_entry(self, table: int, i: int) -> bytes:
        """Decompressed entry i of a pointer table (DATA_TABLE, FIELD_TABLE, TILE_TABLE)."""
        key = i if table == DATA_TABLE else (table, i)
        if key not in self._cache:
            p = hirom(int.from_bytes(self.data[table + 3 * i:table + 3 * i + 3], "little"))
            self._cache[key] = decompress(self.data, p)[0]
        return self._cache[key]

    def name(self, pid: int, sc: int = 0) -> tuple[str, str]:
        """(surname, given name) of person pid as scenario sc spells it."""
        o = NAME_TABLE + NAME_SIZE * (pid + PERSON_COUNT * sc)
        return sjis(self.data[o + 1:o + 7]), sjis(self.data[o + 8:o + 14])

    def persons(self) -> list[dict]:
        out = []
        for pid in range(PERSON_COUNT):
            o = PERSON_TABLE + PERSON_SIZE * pid
            r = self.data[o:o + PERSON_SIZE]
            father = r[8] | r[9] << 8
            out.append({
                "id": pid, "offset": o, "name": "".join(self.name(pid)), "face": r[0] | r[1] << 8,
                "politics_max": 2 * r[2], "war_max": 2 * r[3], "intellect_max": 2 * r[4],
                "charm": r[5], "ambition": r[6], "born": BIRTH_BASE + r[7],
                "father_face": None if father == 0xFFFF else father, "unknown": r[10:12].hex(),
                "flags": r[12] | r[13] << 8,
            })
        return out

    def scenario_persons(self, sc: int) -> list[dict]:
        """The 700 records of scenario sc as the game copies them to $7E:3F70 (35 bytes each):
        +0 person id, +2/+4 list links LE16, +8 政治 戦闘 智謀 (% of the cap), +11 忠誠,
        +12 勲功 LE16 (999 = none), +15 大名, +17 軍団 LE16, +19 城 LE16 (0 = none),
        +23 兵士 訓練 士気, +26 部隊, +27 仕官年数, +31 適性 LE16 (3 bits each: 足軽 騎馬 鉄砲 水軍),
        +33 bits 0-2 status (STATUS), bits 3-5 身分 (RANKS). List links and 大名 / 城 are 1-based record numbers (0 / FFFF = none).
        """
        e = self.entry(SCENARIO_PERSONS + sc)
        out = []
        for k in range(PERSON_COUNT):
            r = e[SCENARIO_PERSON_SIZE * k:SCENARIO_PERSON_SIZE * (k + 1)]
            apt = le16(r, 31)
            out.append({
                "slot": k, "id": le16(r, 0), "raw": r, "politics": r[8], "war": r[9], "intellect": r[10],
                "loyalty": r[11], "merit": le16(r, 12), "daimyo": r[15], "corps": le16(r, 17), "castle": le16(r, 19),
                "status": r[33] & 7, "rank": r[33] >> 3 & 7, "next": le16(r, 4), "prev": le16(r, 2),
                "soldiers": r[23], "training": r[24], "morale": r[25], "unit": r[26], "service": r[27],
                "aptitude": [APTITUDE[apt >> 3 * i & 7] if apt >> 3 * i & 7 < len(APTITUDE) else "?"
                             for i in range(len(UNITS))],
            })
        return out

    def face_palettes(self) -> list[list[int]]:
        d = self.data
        return [[d[FACE_PALETTES + 32 * p + 2 * i] | d[FACE_PALETTES + 32 * p + 2 * i + 1] << 8 for i in range(16)]
                for p in range(FACE_PALETTE_COUNT)]

    def face_palette_number(self, code: int) -> int:
        o = PACK_PALETTE + 2 * ((code & 0x1F) % PACK_COUNT) if code & 0x8000 else PORTRAIT_PALETTE + 2 * code
        return self.data[o] | self.data[o + 1] << 8

    def face_tiles(self, code: int) -> bytes:
        """960 bytes of 4bpp tiles, as the game builds them ($C3:2DF5)."""
        if not code & 0x8000:
            return self.entry(PORTRAIT_ENTRY + code % 410)[:FACE_BYTES]
        pack = (code & 0x1F) % PACK_COUNT
        e = self.entry(PACK_ENTRY + pack)
        face = [e[FACE_BYTES * i:FACE_BYTES * (i + 1)] for i in range(4)]
        top, eyes, mouth = self.data[PACK_ROWS + 3 * pack:PACK_ROWS + 3 * pack + 3]
        s = [code >> shift & 3 for shift in (5, 7, 9, 11)]
        cut = 160 * top
        out = bytearray(face[s[0]][:cut] + face[s[1]][cut:])
        if code & 0x1F == 0:
            out[0x280:0x2A0] = face[s[0]][0x280:0x2A0]
        a = 0x140 + 32 * eyes
        out[a:a + 0x60] = face[s[2]][a:a + 0x60]
        a = 0x280 + 32 * mouth
        n = 32 * self.data[PACK_MOUTH_TILES + pack]
        out[a:a + n] = face[s[3]][a:a + n]
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
        pal = [bgr555_rgb(c) for c in self.face_palettes()[self.face_palette_number(code)]]
        return [pal[v] for v in self.face_pixels(code)]

    def castle_name(self, i: int, sc: int = 0) -> str:
        """Name of castle i (0-based) with its suffix."""
        o = CASTLE_NAMES + CASTLE_NAME_SIZE * (i + CASTLE_COUNT * sc)
        return sjis(self.data[o:o + 9]) + CASTLE_SUFFIX.get(i + 1, "城")

    def castles(self, sc: int) -> list[dict]:
        """+0/+2 list links, +4 first general (1-based record), +8 軍団, +10 城郭, +11 石高 LE16,
        +13 商業, +14 人口 LE16, +16 民忠, +17 徴兵 (人口 and 徴兵 are recomputed at game start)."""
        e = self.entry(SCENARIO_CASTLES + sc)
        out = []
        for i in range(CASTLE_COUNT):
            r = e[CASTLE_SIZE * i:CASTLE_SIZE * (i + 1)]
            out.append({"id": i + 1, "name": self.castle_name(i, sc), "raw": r, "first": le16(r, 4), "corps": le16(r, 8),
                        "walls": r[10], "koku": le16(r, 11), "commerce": r[13], "population": le16(r, 14),
                        "loyalty": r[16], "draft": r[17]})
        return out

    def corps(self, sc: int) -> list[dict]:
        """軍団: +4 居城 (1-based castle), +6 軍団長 (1-based person record), +8 大名 number,
        +11 金 LE16, +13 米 LE16. 大名 n's 当主 is the 軍団長 of its first 軍団."""
        e = self.entry(SCENARIO_CORPS + sc)
        persons = self.scenario_persons(sc)
        out = []
        for i in range(len(e) // CORPS_SIZE):
            r = e[CORPS_SIZE * i:CORPS_SIZE * (i + 1)]
            if not 0 < le16(r, 6) <= PERSON_COUNT:
                continue
            out.append({"id": i + 1, "raw": r, "castle": le16(r, 4), "leader": persons[le16(r, 6) - 1]["id"],
                        "daimyo": le16(r, 8), "gold": le16(r, 11), "rice": le16(r, 13)})
        return out

    def castle_positions(self) -> list[tuple[int, int, int]]:
        """(国, x, y) of the 128 castles on the big map."""
        d = self.data
        return [(d[o], d[o + 7], d[o + 8]) for o in range(CASTLE_INFO, CASTLE_INFO + CASTLE_INFO_SIZE * CASTLE_COUNT,
                                                          CASTLE_INFO_SIZE)]

    def map_cells(self, layer: int) -> list[int]:
        """BG tilemap entries of the big map, row-major (layer 0 terrain, 1 roads)."""
        o = MAP_TILEMAP + 2 * MAP_W * MAP_H * layer
        return [le16(self.data, o + 2 * i) for i in range(MAP_W * MAP_H)]

    def map_palettes(self) -> dict[int, list[int]]:
        d = self.data
        return {3 + p: [le16(d, MAP_PALETTES + 32 * p + 2 * i) for i in range(16)] for p in range(3)}

    def map_pixels(self, roads: bool = True) -> list[tuple[int, int, int]]:
        """The big map, MAP_W x MAP_H tiles, as RGB pixels."""
        e = self.entry(MAP_TILES_ENTRY)
        tiles = [decode_tile(e[32 * k:32 * k + 32]) for k in range(len(e) // 32)]
        pal = {p: [bgr555_rgb(c) for c in cs] for p, cs in self.map_palettes().items()}
        w = MAP_W * 8
        out = [(0, 0, 0)] * (w * MAP_H * 8)
        for layer in (0, 1) if roads else (0,):
            for i, t in enumerate(self.map_cells(layer)):
                px, colours = tiles[(t & 0x3FF) - MAP_TILE0], pal[t >> 10 & 7]
                y0, x0 = i // MAP_W * 8, i % MAP_W * 8
                for k, c in enumerate(px):
                    if layer and not c:
                        continue
                    ty, tx = divmod(k, 8)
                    out[(y0 + (7 - ty if t & 0x8000 else ty)) * w + x0 + (7 - tx if t & 0x4000 else tx)] = colours[c]
        return out

    def field_layers(self, n: int) -> tuple[list[int], list[int]]:
        """(terrain, overlay) tilemaps of field map n, 16 x 12 LE16 entries each, row-major."""
        e = self.table_entry(FIELD_TABLE, n)
        return [le16(e, 2 * i) for i in range(192)], [le16(e, 384 + 2 * i) for i in range(192)]

    def field_cells(self, n: int) -> bytes:
        """8 x 6 terrain cells of field map n (11 = sea; other values not decoded)."""
        return self.table_entry(FIELD_TABLE, FIELD_CELLS + n)

    def field_palettes(self) -> dict[int, list[int]]:
        d = self.data
        return {3 + p: [le16(d, FIELD_PALETTES + 32 * p + 2 * i) for i in range(16)] for p in range(4)}

    def field_pixels(self) -> list[tuple[int, int, int]]:
        """All 330 field maps in their 30 x 11 grid (480 x 132 tiles) as RGB pixels."""
        e = self.table_entry(TILE_TABLE, FIELD_TILES_ENTRY)
        tiles = [decode_tile(e[32 * k:32 * k + 32]) for k in range(len(e) // 32)]
        pal = {p: [bgr555_rgb(c) for c in cs] for p, cs in self.field_palettes().items()}
        w = FIELD_COLS * FIELD_MAP_W * 8
        out = [(0, 0, 0)] * (w * FIELD_ROWS * FIELD_MAP_H * 8)
        for n in range(FIELD_COUNT):
            for layer, cells in enumerate(self.field_layers(n)):
                for i, t in enumerate(cells):
                    if layer and t in (0, 0xFFFF):
                        continue
                    px, colours = tiles[t & 0x3FF], pal[3 + (t >> 10 & 7)]
                    y0 = (n // FIELD_COLS * FIELD_MAP_H + i // FIELD_MAP_W) * 8
                    x0 = (n % FIELD_COLS * FIELD_MAP_W + i % FIELD_MAP_W) * 8
                    for k, c in enumerate(px):
                        if layer and not c:
                            continue
                        ty, tx = divmod(k, 8)
                        out[(y0 + (7 - ty if t & 0x8000 else ty)) * w + x0 + (7 - tx if t & 0x4000 else tx)] = \
                            colours[c]
        return out
