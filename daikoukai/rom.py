"""SFC スーパー大航海時代 (KOEI) ROM decoding.

Offsets are file offsets of the headerless 1 MB LoROM image: CPU $bb:8000-$FFFF = file (bb & 0x7F) * 0x8000
+ (addr - 0x8000). The data and the text encoding are those of the FC version (famicom-re/daikoukai); this
module ports its decoders to the SFC layout. The LZ decompressor ($00:97F3) is the shared tools/koei_lz.py.
See docs/ROM_FORMAT.md.
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Super Daikoukai Jidai (Japan).zip")
LZ_TABLES = 0x1696                      # decompressor table block, routine at $00:97F3 (file 0x17F3)

# ---------------------------------------------------------------- initial game state
INIT = 0xF4FE                           # $01:F4FE: copied to WRAM $7E:DF02 on a new game (= FC bank 57 -> $6000)
INIT_WRAM = 0xDF02
INIT_SIZE = 0x1286
DATA = 0x10784                          # $02:8784: the "DATA file" (handle $7E:1E1C) = FC bank 58; names etc.
PERSON_START, PERSON_SIZE, PERSON_COUNT = 0x542, 7, 41    # WRAM $E444: player + 20 mates + 20 admirals
STAT_START, STAT_SIZE, STAT_COUNT = 0xBBE, 10, 21         # WRAM $EAC0: player + 20 mates
STATS = [("age", "年齡(推定)"), ("leadership", "統率"), ("judgment", "判断"), ("intelligence", "知力"),
         ("courage", "勇気"), ("strength", "強さ")]
NATIONS = ["ポルトガル", "スペイン", "トルコ", "イギリス"]   # flag high nibble (as in the FC version, 推定)
FLEET_START, FLEET_SIZE, FLEET_COUNT = 0x662, 16, 21      # WRAM $E564: fleet records, bytes 0-3 = location
GIRL_NAMES, GIRL_COUNT = 0xC, 20        # DATA + 0x0C: 20 LE16 name offsets
GIRL_FACE = 13                          # girl k shows portrait k + 13 (as in the FC version, 推定)
TOWN_FLAGS = 0xF76                      # WRAM $EE78 + port: building flags

# ---------------------------------------------------------------- ports and names (all in the DATA file)
PORTS, PORT_SIZE, PORT_COUNT = DATA + 0x12D4, 19, 70  # 15-byte name + (chunk x, chunk y, metatile x, metatile y)
PORT_INFO, PORT_INFO_COUNT = DATA + 0x1806, 50        # 5 bytes: region, specialty, ?, item, ?
REGIONS = ["地中海", "北歐", "西非", "東非", "新大陸", "阿拉伯", "遠東", "東南亞"]
NAME_LISTS = {                          # key: (file offset, strings to skip, count)
    "goods": (0x12606, 0, 26),
    "cannons": (0x126C5, 0, 3),
    "figureheads": (0x49C1C, 0, 6),
    "ships": (0x4A7BA, 0, 6),
    "woods": (0x4B324, 0, 4),
    "masts": (0x4B324, 4, 3),
    "sails": (0x4B324, 7, 2),
}

# ---------------------------------------------------------------- faces (5 x 6 tiles, 4bpp, 960 bytes)
FACE_W, FACE_H = 5, 6
FACE_BYTES = FACE_W * FACE_H * 32
PORTRAIT_COUNT = 53
PORTRAITS = [(0xC8002, 33), (0xD0002, 20)]   # $19:8002 faces 0-32, $1A:8002 faces 33-52; 0x3C2-byte records
PORTRAIT_STRIDE = 0x3C2                 # 2-byte header (= index in the bank x 30) + 960 bytes
FACE_PALETTE = DATA + 0x2070            # 32 bytes -> CGRAM $A0 (BG palette 5), shared by every face
COMPOSITE_BASE = 0xD8000                # $1B:8000: composite face parts
COMPOSITE_ADDR = 0xF40C                 # per head 20 LE16 ($1B:8000-relative): top x4, eyes x4, nose x4, mouth x4,
COMPOSITE_TILES = 0xF4AC                # bottom x4; per head 5 x LE16 (first tile, tile count), same group order
COMPOSITE_HEADS = 4
COMPOSITE_GROUPS = ["top", "eyes", "nose", "mouth", "bottom"]
# (slot id, label, code shift) in the order the game copies them ($7E:858D); a later part overwrites whole tiles
COMPOSITE_SLOTS = [("bottom", "下", 0), ("top", "上", 8), ("eyes", "眼", 6), ("nose", "鼻", 4), ("mouth", "口", 2)]

# ---------------------------------------------------------------- world map (same file as FC PRG 0x60000)
MAP = 0x50000
MAP_AREAS_W = 24                        # areas of 3 x 3 chunks
MAP_W, MAP_H = 72, 36                   # chunks of 7 x 7 blocks = 14 x 14 metatiles = 28 x 28 tiles
CHUNK_TILES = 28
MAP_BLOCKS = DATA + 0x28D8              # block -> 4 metatiles (TL, TR, BL, BR), = FC bank 1 $BCCA
MAP_METATILES = DATA + 0x27B0           # 18 x 4 LE16 tilemap entries (TL, TR, BL, BR)
METATILE_COUNT = 18
SEA_METATILES = (0, 17)                 # drawn on BG2; the land metatiles 1-16 on BG1 over sea metatile 0
MAP_BAND = [3, 2, 1, 1, 0, 0, 0, 0, 1, 1, 2, 3]     # graphics set by area row (cy // 3), WRAM $7E:F164
MAP_CHR = 0x80000                       # $10:8000 + 0x900 * band: 0x48 land tiles loaded at tile 0x77
MAP_CHR_TILE, MAP_CHR_COUNT = 0x77, 0x48
MAP_PALETTE = DATA + 0x25B0             # + 0x80 * band + 0x20 * frame: BG palette 2 (4 animation frames)
# Sea tiles (4 per sea metatile) of the animation frame seen right after leaving port: VRAM tile -> file offset.
# The other frames and their order are not decoded.
SEA_CHR = {0xBF: 0x83F3E, 0xC3: 0x83FBE, 0xC7: 0x83F7E, 0xCB: 0x83EFE,
           0xCF: 0x84F3E, 0xD3: 0x84FBE, 0xD7: 0x84F7E, 0xDB: 0x84EFE}

# ---------------------------------------------------------------- port towns (BG2, one layout for every port)
TOWN_FILE = 0x1423C                     # $02:C23C: "graphics map" file (handle $7E:1E0E), LE16 BG tilemap entries
DARK_COPY = 0xA0DA                      # the dark (night) copy of each tilemap is this far into the file
TOWN_FRAME = (0x823A, 1, 1, 30, 27)     # (file pos, x, y, w, h) on BG2
TOWN_PICTURE = [(0x21C2, 2, 5, 28, 8), (0x2382, 2, 13, 28, 7)]
TOWN_AFTER = [(0x80B2, 2, 20, 28, 7), (0x800A, 2, 18, 18, 2), (0x808A, 20, 20, 10, 2)]
# Pieces over the picture (piece table $06:EE2A, drawn one row higher than the table says):
# (file pos, x, y, w, h, flag mask, flag value); trading ports only
TOWN_PIECES = [(0x250A, 2, 5, 7, 4, 0x04, 0x04), (0x2632, 23, 5, 7, 5, 0x10, 0x10),
               (0x25B2, 2, 11, 7, 4, 0, 0), (0x257A, 16, 5, 7, 4, 0, 0), (0x2542, 9, 5, 7, 4, 0, 0),
               (0x25EA, 24, 13, 6, 6, 0, 0)]
TOWN_W, TOWN_H = 32, 28                 # rendered area: BG2 tilemap rows/columns 0-31 x 0-27
# BG CHR of the town screen (VRAM tile -> source): water $16:8B6D (first animation frame), LZ $16:8000,
# raw $12:8000
TOWN_CHR_RAW = [(0x77, 0xB0B6D, 0x20), (0x1A0, 0x90000, 0x1C1)]
TOWN_CHR_LZ = 0xB0000                   # $16:8000, decompressed to $7F:0000
TOWN_CHR_LZ_LOADS = [(0x97, 0, 0xBD), (0x3A5, 0x17A0, 0x0B)]   # (VRAM tile, offset in the output, tiles)
# CGRAM: 8 palettes from DATA + 0x1FD0, then palettes 2 and 6 from DATA + 0x2A70 / + 0x2B70
TOWN_PALETTES = [DATA + 0x1FD0 + 32 * p for p in range(8)]
TOWN_PALETTES[2], TOWN_PALETTES[6] = DATA + 0x2A70, DATA + 0x2B70


def le16(b: bytes, o: int) -> int:
    return b[o] | b[o + 1] << 8


def text(raw: bytes) -> str:
    """Half-width kana text up to the first 0: hiragana by default, ESC K / ESC H switch katakana on / off."""
    out, kata, i = "", False, 0
    raw = raw.split(b"\0")[0]
    while i < len(raw):
        b = raw[i]
        if b == 0x1B and i + 1 < len(raw):
            kata = raw[i + 1] == 0x4B
            i += 2
            continue
        if 0xA1 <= b <= 0xDF:
            c = unicodedata.normalize("NFKC", bytes([b]).decode("cp932"))
            if not kata and "ァ" <= c <= "ヶ":
                c = chr(ord(c) - 0x60)
            out += c
        elif b == 0x2D:
            out += "ー"
        elif 0x20 <= b < 0x7F:
            out += chr(b)
        else:
            out += f"<{b:02X}>"
        i += 1
    return unicodedata.normalize("NFC", out.replace("ﾞ", "゙").replace("ﾟ", "゚"))


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
    return data[len(data) % 0x8000:]  # drop a 512-byte copier header if present


def is_composite(code: int) -> bool:
    return code >= 0x1000


def decode_face_code(code: int) -> tuple[int, list[int]]:
    """Composite face code -> (head, page per slot in COMPOSITE_SLOTS order)."""
    return code >> 10 & 3, [code >> shift & 3 for _, _, shift in COMPOSITE_SLOTS]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = load_rom_bytes(path)
        self._lz = {}

    def u16(self, o: int) -> int:
        return le16(self.data, o)

    def lz(self, offset: int) -> bytes:
        if offset not in self._lz:
            self._lz[offset] = koei_lz.decompress(self.data, offset, LZ_TABLES)[0]
        return self._lz[offset]

    def palette(self, o: int) -> list[tuple[int, int, int]]:
        return [bgr555_rgb(self.u16(o + 2 * i)) for i in range(16)]

    # ------------------------------------------------------------ people

    def init(self, wram: int, n: int) -> bytes:
        """Initial value of WRAM $7E:wram.. (n bytes)."""
        return self.data[INIT + wram - INIT_WRAM:][:n]

    def data_text(self, offset: int) -> str:
        return text(self.data[DATA + offset:DATA + offset + 32])

    def persons(self) -> list[dict]:
        """41 person records (WRAM $E444): player, 20 mates, 4 nations x 5 admirals."""
        out = []
        for k in range(PERSON_COUNT):
            r = self.data[INIT + PERSON_START + PERSON_SIZE * k:][:PERSON_SIZE]
            ptr = le16(r, 0)
            # the player's name points into WRAM (default レオン, part of the initial block)
            name = text(self.init(ptr, 16)) if ptr >= INIT_WRAM else self.data_text(ptr)
            out.append({"id": k, "name": name, "name_ptr": ptr, "battle": r[2], "sailing": r[3],
                        "face": le16(r, 4), "nation": NATIONS[r[6] >> 4], "flags": r[6],
                        "role": "主角" if k == 0 else "航海士" if k <= 20 else "提督"})
        for k in range(STAT_COUNT):
            r = self.data[INIT + STAT_START + STAT_SIZE * k:][:STAT_SIZE]
            out[k].update(zip([key for key, _ in STATS], r))
            out[k]["stat_raw"] = r[len(STATS):]
        return out

    def girls(self) -> list[dict]:
        return [{"id": k, "name": self.data_text(self.u16(DATA + GIRL_NAMES + 2 * k)), "face": k + GIRL_FACE}
                for k in range(GIRL_COUNT)]

    def fleets(self) -> list[dict]:
        """Initial fleet records (WRAM $E564, 16 bytes): bytes 0-3 = location (chunk x/y, metatile x/y)."""
        out = []
        for k in range(FLEET_COUNT):
            r = self.data[INIT + FLEET_START + FLEET_SIZE * k:][:FLEET_SIZE]
            out.append({"id": k, "loc": tuple(r[:4]), "raw": r})
        return out

    # ------------------------------------------------------------ ports and names

    def name_list(self, key: str) -> list[str]:
        o, skip, n = NAME_LISTS[key]
        return [text(p) for p in self.data[o:o + 0x400].split(b"\0")[skip:skip + n]]

    def town_flags(self, p: int) -> int:
        return self.data[INIT + TOWN_FLAGS + p]

    def ports(self) -> list[dict]:
        goods = self.name_list("goods")
        out = []
        for p in range(PORT_COUNT):
            o = PORTS + PORT_SIZE * p
            cx, cy, mx, my = self.data[o + 15:o + 19]
            d = {"id": p, "name": text(self.data[o:o + 15]), "chunk_x": cx, "chunk_y": cy, "mt_x": mx, "mt_y": my,
                 "supply": p >= PORT_INFO_COUNT, "flags": self.town_flags(p)}
            if p < PORT_INFO_COUNT:
                region, special, unk, item, unk4 = self.data[PORT_INFO + 5 * p:][:5]
                d.update(region=REGIONS[region], specialty=goods[special] if special < len(goods) else "",
                         byte2=unk, item=item if item != 0xFF else "", byte4=unk4)
            out.append(d)
        return out

    # ------------------------------------------------------------ faces

    def portrait(self, n: int) -> bytes:
        """960 bytes (30 tiles, row-major 5 x 6) of portrait n."""
        for base, count in PORTRAITS:
            if n < count:
                o = base + PORTRAIT_STRIDE * n
                return self.data[o:o + FACE_BYTES]
            n -= count
        raise IndexError(n)

    def composite_part(self, head: int, slot: str, page: int) -> tuple[int, bytes]:
        """(first tile, bytes) of one composite part: whole tiles copied into the 960-byte face."""
        g = COMPOSITE_GROUPS.index(slot)
        src = COMPOSITE_BASE + self.u16(COMPOSITE_ADDR + 40 * head + 8 * g + 2 * page)
        first, count = self.u16(COMPOSITE_TILES + 20 * head + 4 * g), self.u16(COMPOSITE_TILES + 20 * head + 4 * g + 2)
        return first, self.data[src:src + 32 * count]

    def composite(self, code: int) -> bytes:
        head, pages = decode_face_code(code)
        buf = bytearray(FACE_BYTES)
        for (slot, _, _), page in zip(COMPOSITE_SLOTS, pages):
            first, raw = self.composite_part(head, slot, page)
            buf[32 * first:32 * first + len(raw)] = raw
        return bytes(buf)

    def face(self, code: int) -> bytes:
        return self.composite(code) if is_composite(code) else self.portrait(code)

    def face_pixels(self, code: int) -> bytes:
        """40 x 48 colour numbers 0-15 (FACE_PALETTE)."""
        return tiles_pixels(self.face(code), FACE_W, FACE_H)

    def face_rgb(self, code: int) -> list[tuple[int, int, int]]:
        pal = self.palette(FACE_PALETTE)
        return [pal[c] for c in self.face_pixels(code)]

    # ------------------------------------------------------------ world map

    def chunk_blocks(self, cx: int, cy: int) -> bytes:
        """7 x 7 block ids of chunk (cx, cy)."""
        area = self.u16(MAP + 4 + 5 * (cy // 3 * MAP_AREAS_W + cx // 3))
        k = self.u16(MAP + self.u16(MAP) + 18 * area + 2 * (cy % 3 * 3 + cx % 3))
        o = MAP + self.u16(MAP + 2) + 49 * k
        return self.data[o:o + 49]

    def chunk_metatiles(self, cx: int, cy: int) -> list[int]:
        """14 x 14 metatile ids of chunk (cx, cy), row-major."""
        out = [0] * 196
        for b, block in enumerate(self.chunk_blocks(cx, cy)):
            for q in range(4):
                out[(b // 7 * 2 + q // 2) * 14 + b % 7 * 2 + q % 2] = self.data[MAP_BLOCKS + 4 * block + q]
        return out

    def metatile_entries(self, m: int) -> list[int]:
        return [self.u16(MAP_METATILES + 8 * m + 2 * q) for q in range(4)]

    def chunk_tilemaps(self, cx: int, cy: int) -> tuple[list[int], list[int]]:
        """BG1 (land) and BG2 (sea) tilemap entries, 28 x 28, of chunk (cx, cy) as the game draws it."""
        bg1, bg2 = [0] * CHUNK_TILES ** 2, [0] * CHUNK_TILES ** 2
        sea = self.metatile_entries(0)
        for i, m in enumerate(self.chunk_metatiles(cx, cy)):
            land = m not in SEA_METATILES
            for q, (e1, e2) in enumerate(zip(self.metatile_entries(m) if land else [0] * 4,
                                             sea if land else self.metatile_entries(m))):
                j = (i // 14 * 2 + q // 2) * CHUNK_TILES + i % 14 * 2 + q % 2
                bg1[j], bg2[j] = e1, e2
        return bg1, bg2

    def map_band(self, cy: int) -> int:
        return MAP_BAND[cy // 3]

    def map_chr(self, band: int) -> dict[int, bytes]:
        """VRAM tile -> 32 bytes, for the tiles the map metatiles use."""
        o = MAP_CHR + 0x900 * band
        out = {MAP_CHR_TILE + i: self.data[o + 32 * i:o + 32 * i + 32] for i in range(MAP_CHR_COUNT)}
        out.update({t: self.data[s:s + 32] for t, s in SEA_CHR.items()})
        return out

    def map_palette(self, band: int, frame: int = 0) -> int:
        return MAP_PALETTE + 0x80 * band + 0x20 * frame

    def metatile_pixels(self, band: int, m: int) -> list[tuple[int, int, int]]:
        """16 x 16 RGB of metatile m (land over sea), palette frame 0."""
        chr_, pal = self.map_chr(band), self.palette(self.map_palette(band))
        sea = self.metatile_entries(0 if m not in SEA_METATILES else m)
        land = self.metatile_entries(m) if m not in SEA_METATILES else [0] * 4
        out = [(0, 0, 0)] * 256
        for q in range(4):
            for e in (sea[q], land[q]):
                if not e:
                    continue
                for i, c in enumerate(tile_entry_pixels(chr_[e & 0x3FF], e)):
                    if c:
                        out[(q // 2 * 8 + i // 8) * 16 + q % 2 * 8 + i % 8] = pal[c]
        return out

    # ------------------------------------------------------------ port towns

    def town_draws(self, p: int, flags: int | None = None) -> list[tuple[int, int, int, int, int]]:
        """BG2 draws of port p's town (svc $1E from the graphics map file): (file pos, x, y, w, h), in order.
        Trading ports add the pieces their building flags select (default: the new-game values)."""
        f = self.town_flags(p) if flags is None else flags
        draws = [TOWN_FRAME, *TOWN_PICTURE]
        if p < PORT_INFO_COUNT:
            draws += [(pos, x, y, w, h) for pos, x, y, w, h, mask, value in TOWN_PIECES if f & mask == value]
        return draws + TOWN_AFTER

    def town_tilemap(self, p: int, flags: int | None = None) -> list[int]:
        """BG2 tilemap entries, TOWN_W x TOWN_H, of the day picture."""
        tm = [0] * (TOWN_W * TOWN_H)
        for pos, x, y, w, h in self.town_draws(p, flags):
            for i in range(w * h):
                tm[(y + i // w) * TOWN_W + x + i % w] = self.u16(TOWN_FILE + pos + 2 * i)
        return tm

    def town_chr(self) -> dict[int, bytes]:
        out = {}
        for tile, src, n in TOWN_CHR_RAW:
            out.update({tile + i: self.data[src + 32 * i:src + 32 * i + 32] for i in range(n)})
        raw = self.lz(TOWN_CHR_LZ)
        for tile, src, n in TOWN_CHR_LZ_LOADS:
            out.update({tile + i: raw[src + 32 * i:src + 32 * i + 32] for i in range(n)})
        return out

    def town_rgb(self, p: int, flags: int | None = None) -> list[tuple[int, int, int]]:
        """TOWN_W*8 x TOWN_H*8 RGB of the town picture (colour 0 = black)."""
        chr_, pals = self.town_chr(), [self.palette(o) for o in TOWN_PALETTES]
        return tilemap_rgb(self.town_tilemap(p, flags), TOWN_W, TOWN_H, chr_, pals)


def tiles_pixels(raw: bytes, w: int, h: int) -> bytes:
    """w x h 4bpp tiles stored row-major -> (8w x 8h) colour numbers."""
    out = bytearray(w * h * 64)
    for t in range(w * h):
        for i, c in enumerate(decode_tile(raw[32 * t:32 * t + 32])):
            out[(t // w * 8 + i // 8) * w * 8 + t % w * 8 + i % 8] = c
    return bytes(out)


def tile_entry_pixels(raw: bytes, e: int) -> list[int]:
    """Colour numbers of a tile drawn with tilemap entry e (h/v flip applied)."""
    px = decode_tile(raw)
    if e & 0x4000:
        px = [px[y * 8 + 7 - x] for y in range(8) for x in range(8)]
    if e & 0x8000:
        px = [px[(7 - y) * 8 + x] for y in range(8) for x in range(8)]
    return px


def tilemap_rgb(tm: list[int], w: int, h: int, chr_: dict[int, bytes], pals: list[list]) -> list[tuple]:
    out = [(0, 0, 0)] * (w * h * 64)
    for j, e in enumerate(tm):
        if not e or (e & 0x3FF) not in chr_:
            continue
        pal = pals[e >> 10 & 7]
        for i, c in enumerate(tile_entry_pixels(chr_[e & 0x3FF], e)):
            if c:
                out[(j // w * 8 + i // 8) * w * 8 + j % w * 8 + i % 8] = pal[c]
    return out
