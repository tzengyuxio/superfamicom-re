"""SFC 信長の野望・覇王伝 (KOEI, 1993) ROM decoding.

Offsets are file offsets of the headerless 2 MB HiROM image (CPU $C0:0000 = file 0). See docs/ROM_FORMAT.md.
The LZ decompressor is the shared one in tools/koei_lz.py. Both the original release and Rev 1 are supported:
Rev 1 moves most tables, so the offsets are kept per revision (OFFSETS), told apart by the decompressor table
position that koei_lz.find_tables finds.
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Nobunaga no Yabou - Haouden (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

# Per-revision file offsets (key: decompressor table offset). Everything not listed is the same in both.
OFFSETS = {
    0xA0D9: {  # original release
        "rev": 0,
        "entries": 0x7BD84,             # 810 long pointers to LZ streams ("entries" below)
        "images": [0xB0000, 0xB672F, 0x9900C],
        "future": [0xA3D7E, 0x97950, 0x98904],
        "provinces": 0x297EA, "titles": 0x28896, "treasures": 0x29226, "battles": 0x29ADE,
        "stat_names": 0x2A94C, "princesses": 0x3A8AC, "terrains": 0xA5FE4,
        "face_parts": 0x1B0A7, "face_table": 0x1B9EC, "face_table2": 0x1B9A4, "face_palette": 0xA8C6D,
        "map_palettes": {2: 0xA8CED, 3: 0xA8D0D},
        "siege_types": 0x28148, "battle_castles": 0x5F4DE, "castle_xy": 0x5ED80,
        "battle_meta": 0xACD5A, "battle_flip": 0xAD14E, "overlay_meta": 0xACF5A, "overlay_flip": 0xAD34E,
        "metatiles": 0xAD54E, "battle_palettes": 0xA9353,
    },
    0xA0D3: {  # Rev 1
        "rev": 1,
        "entries": 0x7C422,
        "images": [0xB0000, 0xB672F, 0x986EC],
        "future": [0xA4112, 0x97030, 0x97FE4],
        "provinces": 0x2B17D, "titles": 0x2A229, "treasures": 0x2ABB9, "battles": 0x2B471,
        "stat_names": 0x2C2DF, "princesses": 0x3B130, "terrains": 0xA6378,
        "face_parts": 0x1B994, "face_table": 0x1C2D9, "face_table2": 0x1C291, "face_palette": 0xA9001,
        "map_palettes": {2: 0xA9081, 3: 0xA90A1},
        "siege_types": 0x29ADB, "battle_castles": 0x5F961, "castle_xy": 0x5F205,
        "battle_meta": 0xAD0EE, "battle_flip": 0xAD4E2, "overlay_meta": 0xAD2EE, "overlay_flip": 0xAD6E2,
        "metatiles": 0xAD8E2, "battle_palettes": 0xA96E7,
    },
}
ENTRY_COUNT = 810

# Font: glyph g = 16x16 1bpp, 32 bytes at FONT + 32 g (top-left, top-right, bottom-left, bottom-right 8x8 tiles,
# one byte per row). Text code 0x8140 + g, big-endian. A code whose low byte would be 00 is written
# 0x9140 + k (= 0x8200 + 0x100 k). Codes 0x8981-0x913F draw a blank cell.
FONT = 0x1F0000
GLYPH_COUNT = 1808
LIGATURES = {(1804, 1805, 1806): "長宗我部", (1807, 1805, 1806): "香宗我部"}

# Scenario images: the game copies 0x6303 bytes of scenario s to $7E:2000 (and the common block COMMON to
# $7E:8303) when a game starts ($C3:0AD1). Record tables inside (WRAM address = 0x2000 + image offset):
SCENARIO_COUNT = 3
SCENARIO_YEARS = [1551, 1568, 1582]
IMAGE_SIZE = 0x6303
COMMON, COMMON_SIZE = 0xB6303, 0x42D
WRAM_BASE = 0x2000
DAIMYO, DAIMYO_COUNT, DAIMYO_SIZE = 0x20E1, 64, 39
PERSONS, PERSON_COUNT, PERSON_SIZE = 0x2AA1, 460, 39
CASTLES, CASTLE_COUNT, CASTLE_SIZE = 0x70B5, 110, 38
FUTURE_SIZE = 30
BIRTH_BASE = 1476
STATS = ["政治", "戦闘", "智謀", "采配", "野望"]
PERSON_ID_COUNT = 820                   # person ids 0-819 (139, 140, 456 unused)

# String tables: 3-byte pointers to NUL-terminated strings
STRING_TABLES = {"provinces": 64, "titles": 226, "treasures": 120, "battles": 15, "stat_names": 8,
                 "princesses": 93, "terrains": 15}

# Faces: 40x48 = 5x6 4bpp tiles row-major (960 bytes), built by $C1:187F(.., id). Portraits are LZ entries
# FACE_ENTRY + n; composed faces are 5 parts of a group's part pool (see Rom.face_source / composite).
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
FACE_ENTRY = 93
FACE_ID_COUNT = 0x3A1                   # face ids 0-928 ...
FACE_GAP = (0x398, 0x39A)               # ... except 920 and 921
FACE_GROUP_LIMITS = (0x160, 0x1EC, 0x278, 0x304, 0x36E)
FACE_GROUP_COUNT = 6
FACE_PART_COUNT = 5
FACE_PART_VARIANTS = 5
FACE_POOL = 0x17908B                    # group g pool at FACE_POOL + 0x12C0 g
FACE_POOL_SIZE = 0x12C0

# Big map: one BG of 16x16 tiles, 96 x 32 LE16 tilemap = LZ entry MAP_TILEMAP; tiles = entry MAP_CHARS at VRAM
# 0x8400 with the BG character base at 0x8000 (so tile number n is entry byte 32 n - 0x400); CGRAM palettes 2-3.
MAP_TILEMAP, MAP_CHARS = 15, 14
MAP_W, MAP_H = 96, 32
MAP_CHR_SKIP = 0x400

# Battle maps 0-142 = LZ entries BATTLE_ENTRY + m: hex grid of 40 columns x 23 rows stored column by column,
# 2 bytes per cell (ground code, overlay code / FF). Odd columns are 8 px lower. Each code is a 2x2-tile
# metatile (metatile table METATILES, flips bit 0 = horizontal, bit 1 = vertical); overlay codes use metatile
# 80 + overlay_meta[code]. Tiles = LZ entry BATTLE_CHARS at VRAM 0x8200 (character base 0x8000).
# CGRAM palettes 2-4 from one of 3 sets of 0x60 bytes at battle_palettes. LZ entry BATTLE_EDGE holds 40 bytes
# per map: (ground, overlay) of the half cell above each odd column (only its bottom half is drawn, in row 0).
BATTLE_ENTRY = 466
BATTLE_EDGE = 609
BATTLE_COUNT = 143
BATTLE_W, BATTLE_H = 40, 23
BATTLE_CHARS = 441
BATTLE_CHR_SKIP = 0x200
BATTLE_OVERLAY_BASE = 80
BATTLE_PALETTE_SETS = 3
CASTLE_MAPS = 110                       # map m < 110: the map around castle m, castle drawn in (see docs)
HISTORIC_FIRST = 111                    # maps 111-125: the 15 historic battles
TERRAIN_FIRST = 126                     # maps 126-142: maps without a castle, picked by the castle's family


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


def load_charset(path: str = CHARSET) -> str:
    with open(path, encoding="utf-8") as f:
        cs = "".join(line.rstrip("\n") for line in f if not line.startswith("#"))
    assert len(cs) == GLYPH_COUNT, len(cs)
    return cs


def face_group(fid: int) -> int:
    for g, lim in enumerate(FACE_GROUP_LIMITS):
        if fid < lim:
            return g
    return 5


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.lz_tables = koei_lz.find_tables(self.data)
        self.off = OFFSETS[self.lz_tables]
        self.rev = self.off["rev"]
        self.charset = load_charset()
        self._cache: dict[int, bytes] = {}

    # --- generic ---
    def entry(self, i: int) -> bytes:
        """Decompressed LZ entry i (0-809) of the entry pointer table."""
        if i not in self._cache:
            t = self.off["entries"] + 3 * i
            p = hirom(int.from_bytes(self.data[t:t + 3], "little"))
            self._cache[i] = koei_lz.decompress(self.data, p, self.lz_tables)[0]
        return self._cache[i]

    def glyph(self, g: int) -> list[list[int]]:
        """16 rows of 16 pixels (1 = ink) of font glyph g."""
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    def glyphs(self, raw: bytes) -> list:
        """Text bytes -> list of glyph numbers (None = blank cell), up to NUL; other bytes as ('ctl', byte)."""
        out, i = [], 0
        while i < len(raw) and raw[i]:
            c = raw[i]
            if 0x81 <= c <= 0x91 and i + 1 < len(raw):
                code = c << 8 | raw[i + 1]
                if code >= 0x9140:
                    code = 0x8200 + ((code - 0x9140) << 8)
                g = code - 0x8140
                out.append(g if 0 <= g < GLYPH_COUNT else None)
                i += 2
            else:
                out.append(("ctl", c))
                i += 1
        return out

    def text(self, raw: bytes) -> str:
        """Game string -> str (stops at NUL). Control bytes become [xx]."""
        gs = self.glyphs(raw)
        out, i = [], 0
        while i < len(gs):
            lig = next((s for k, s in LIGATURES.items() if tuple(gs[i:i + 3]) == k), None)
            if lig:
                out.append(lig)
                i += 3
                continue
            g = gs[i]
            out.append("　" if g is None else f"[{g[1]:02x}]" if isinstance(g, tuple) else self.charset[g])
            i += 1
        return "".join(out)

    def string_table(self, name: str) -> list[str]:
        base = self.off[name]
        out = []
        for i in range(STRING_TABLES[name]):
            p = hirom(int.from_bytes(self.data[base + 3 * i:base + 3 * i + 3], "little"))
            out.append(self.text(self.data[p:self.data.index(b"\0", p) + 1]))
        return out

    # --- scenarios ---
    def image(self, sc: int) -> bytes:
        """The 0x6303-byte scenario image the game copies to $7E:2000."""
        o = self.off["images"][sc]
        return self.data[o:o + IMAGE_SIZE]

    def common(self) -> bytes:
        """The block copied to $7E:8303 for every scenario (contents unsolved)."""
        return self.data[COMMON:COMMON + COMMON_SIZE]

    def name(self, r: bytes) -> tuple[str, str]:
        """(surname, given name) of a 14-byte name field (2 x 7 bytes)."""
        return self.text(r[0:7]), self.text(r[7:14])

    def scenario_persons(self, sc: int) -> list[dict]:
        """460 slots of 39 bytes at $7E:2AA1 (slots with an empty name skipped). See docs/ROM_FORMAT.md."""
        img = self.image(sc)
        out = []
        for k in range(PERSON_COUNT):
            a = PERSONS - WRAM_BASE + PERSON_SIZE * k
            r = img[a:a + PERSON_SIZE]
            if r[2] == 0:
                continue
            p = {"slot": k, "addr": PERSONS + PERSON_SIZE * k, "raw": r, "next": le16(r, 0),
                 "surname": self.name(r[2:16])[0], "given": self.name(r[2:16])[1], "born": BIRTH_BASE + r[16],
                 "b22": r[22], "b23": r[23], "b24": r[24], "b25": r[25], "castle": r[26], "b27": r[27],
                 "b28": r[28], "loyalty": r[29], "kiai": r[30] & 15, "b30_hi": r[30] >> 4, "id": le16(r, 31),
                 "fiefs": r[33], "tail": r[34:39].hex()}
            for i, s in enumerate(STATS):
                p[s] = r[17 + i]
            out.append(p)
        return out

    def future_persons(self, sc: int) -> list[dict]:
        """Persons that appear later: 30-byte records at future[sc], terminated by an empty name."""
        p = self.off["future"][sc]
        out = []
        while self.data[p + 4]:
            r = self.data[p:p + FUTURE_SIZE]
            f = {"no": len(out), "raw": r, "year": BIRTH_BASE + r[0], "b1": r[1], "b2": r[2], "castle": r[3],
                 "surname": self.name(r[4:18])[0], "given": self.name(r[4:18])[1], "born": BIRTH_BASE + r[18],
                 "b24": r[24], "b25": r[25], "id": le16(r, 26), "tail": r[28:30].hex()}
            for i, s in enumerate(STATS):
                f[s] = r[19 + i]
            out.append(f)
            p += FUTURE_SIZE
        return out

    def scenario_castles(self, sc: int) -> list[dict]:
        """110 castles of 38 bytes at $7E:70B5. See docs/ROM_FORMAT.md."""
        img = self.image(sc)
        out = []
        for k in range(CASTLE_COUNT):
            a = CASTLES - WRAM_BASE + CASTLE_SIZE * k
            r = img[a:a + CASTLE_SIZE]
            out.append({"id": k, "addr": CASTLES + CASTLE_SIZE * k, "raw": r, "head0": le16(r, 0),
                        "lord": le16(r, 2), "name": self.text(r[4:10]), "province": r[13], "daimyo": le16(r, 14),
                        "size": r[16] & 0x7F, "main": r[16] >> 7, "defense": r[17], "kan": le16(r, 18),
                        "b20": r[20], "people": r[21], "commerce": r[22], "training": r[23],
                        "soldiers": le16(r, 24), "money": le16(r, 26), "food": le16(r, 28), "guns": le16(r, 30),
                        "horses": le16(r, 32), "order": r[34], "tail": r[35:38].hex()})
        return out

    def scenario_daimyo(self, sc: int) -> list[dict]:
        """64 daimyo slots of 39 bytes at $7E:20E1 (+0 = 0: empty slot). See docs/ROM_FORMAT.md."""
        img = self.image(sc)
        out = []
        for k in range(DAIMYO_COUNT):
            a = DAIMYO - WRAM_BASE + DAIMYO_SIZE * k
            r = img[a:a + DAIMYO_SIZE]
            out.append({"slot": k, "addr": DAIMYO + DAIMYO_SIZE * k, "raw": r, "head": le16(r, 0), "b2": r[2],
                        "relations": r[3:34].hex(), "contribution": r[34], "b35": r[35], "b36": r[36],
                        "b37": r[37], "crest": r[38]})
        return out

    def scenario(self, sc: int) -> dict:
        """Persons, castles and daimyo of a scenario with the WRAM pointers resolved."""
        persons = self.scenario_persons(sc)
        by_addr = {p["addr"]: p for p in persons}
        castles = self.scenario_castles(sc)
        daimyo = [d for d in self.scenario_daimyo(sc) if d["head"]]
        d_by_addr = {d["addr"]: d for d in daimyo}
        for c in castles:
            members, a = [], c["lord"]
            while a and len(members) < PERSON_COUNT:
                members.append(by_addr[a])
                a = by_addr[a]["next"]
            c["members"] = members
            c["daimyo_slot"] = d_by_addr[c["daimyo"]]["slot"] if c["daimyo"] else None
        for d in daimyo:
            d["head_person"] = by_addr[d["head"]]
            d["castles"] = [c for c in castles if c["daimyo"] == d["addr"]]
        return {"persons": persons, "castles": castles, "daimyo": daimyo}

    def person_master(self) -> dict[int, dict]:
        """Person id -> first record (scenario 1-3, then the later-appearing lists) plus every name used."""
        out: dict[int, dict] = {}
        for sc in range(SCENARIO_COUNT):
            for kind, recs in (("start", self.scenario_persons(sc)), ("future", self.future_persons(sc))):
                for r in recs:
                    m = out.setdefault(r["id"], {"id": r["id"], "first": r, "names": [], "appear": []})
                    n = r["surname"] + r["given"]
                    if n not in m["names"]:
                        m["names"].append(n)
                    m["appear"].append((sc, kind, r))
        return dict(sorted(out.items()))

    # --- faces ---
    def face_source(self, fid: int) -> tuple:
        """('entry', n) = LZ entry FACE_ENTRY + n, or ('comp', group, code), as $C1:187F decides."""
        d = self.data
        if fid < 0xD3:
            return ("entry", 12 + fid)
        if fid < 0x36E:
            w = le16(d, self.off["face_table"] + 2 * (fid - 0xD3))
            return ("entry", 12 + (w & 0x7FFF)) if w & 0x8000 else ("comp", face_group(fid), w)
        if fid < 0x37A:
            return ("entry", fid - 0x36E)
        if fid < 0x392:
            return ("comp", 5, le16(d, self.off["face_table2"] + 2 * (fid - 0x36E)))
        if fid < 0x398:
            return ("entry", fid - 0x24B)
        if 0x39A <= fid < FACE_ID_COUNT:
            return ("entry", fid - 0x24D)
        raise ValueError(f"face id {fid:#x} is not handled by $C1:187F (it reuses a stale stack value)")

    def face_ids(self) -> list[int]:
        """Face ids $C1:187F builds: 0-0x397 and 0x39A-0x3A0."""
        return [i for i in range(FACE_ID_COUNT) if not FACE_GAP[0] <= i < FACE_GAP[1]]

    def face_part(self, g: int, p: int) -> tuple[int, int, int]:
        """(mask of cells 0-14, mask of cells 15-29, tiles per variant) of part p of group g."""
        o = self.off["face_parts"] + 48 * p + 6 * g
        return le16(self.data, o), le16(self.data, o + 2), le16(self.data, o + 4)

    def face_part_tiles(self, g: int, p: int, v: int) -> dict[int, bytes]:
        """{cell: 32 tile bytes} that variant v of part p of group g writes."""
        src = FACE_POOL + FACE_POOL_SIZE * g + sum(32 * FACE_PART_VARIANTS * self.face_part(g, q)[2]
                                                   for q in range(p))
        m1, m2, cnt = self.face_part(g, p)
        src += 32 * cnt * v
        out = {}
        for t in range(FACE_W * FACE_H):
            if (m1 if t < 15 else m2) >> (15 - t % 15) & 1:
                out[t] = self.data[src:src + 32]
                src += 32
        return out

    def composite(self, g: int, code: int) -> bytes:
        out = bytearray(FACE_BYTES)
        for p in range(FACE_PART_COUNT):
            for t, raw in self.face_part_tiles(g, p, code >> (3 * p) & 7).items():
                out[32 * t:32 * t + 32] = raw
        return bytes(out)

    def face_tiles(self, fid: int) -> bytes:
        s = self.face_source(fid)
        if s[0] == "entry":
            return self.entry(FACE_ENTRY + s[1])[:FACE_BYTES]
        return self.composite(s[1], s[2])

    def face_palette(self) -> list[int]:
        """The one face palette (OBJ palette 7 = CGRAM 0xF0-0xFF, copied by $C1:08CC)."""
        o = self.off["face_palette"]
        return [le16(self.data, o + 2 * i) for i in range(16)]

    def face_pixels(self, fid: int = 0, tiles: bytes | None = None) -> list[int]:
        """40x48 colour numbers, row-major."""
        tiles = self.face_tiles(fid) if tiles is None else tiles
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, fid: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(fid)]

    # --- big map ---
    def map_palettes(self) -> dict[int, list[int]]:
        return {p: [le16(self.data, o + 2 * i) for i in range(16)] for p, o in self.off["map_palettes"].items()}

    def map_tilemap(self) -> list[int]:
        t = self.entry(MAP_TILEMAP)
        return [le16(t, 2 * i) for i in range(MAP_W * MAP_H)]

    def map_rgb(self) -> list[tuple[int, int, int]]:
        """(MAP_W*16) x (MAP_H*16) RGB tuples."""
        chars = bytes(MAP_CHR_SKIP) + self.entry(MAP_CHARS)
        pals = {p: [bgr555_rgb(c) for c in v] for p, v in self.map_palettes().items()}
        return render_cells(self.map_tilemap(), MAP_W, MAP_H, chars, pals)

    def castle_cells(self) -> list[tuple[int, int]]:
        """Big-map cell (column, row) of each castle's icon: table $C5:ED80 (x, y bytes, read by $C2:4BA1) + 1, as
        the map cell writer $C2:3636 adds. 本城 icons (castle +16 bit 7) also take the cell above."""
        o = self.off["castle_xy"]
        return [(self.data[o + 2 * k] + 1, self.data[o + 2 * k + 1] + 1) for k in range(CASTLE_COUNT)]

    # --- battle maps ---
    def battle_edge(self, m: int) -> list[tuple[int, int]]:
        """(ground, overlay) of the half cell above odd column 2k+1, k = 0-19."""
        e = self.entry(BATTLE_EDGE)[40 * m:40 * m + 40]
        return [(e[2 * k], e[2 * k + 1]) for k in range(BATTLE_W // 2)]

    def battle_cells(self, m: int) -> list[list[tuple[int, int]]]:
        """[column][row] -> (ground code, overlay code or 0xFF)."""
        e = self.entry(BATTLE_ENTRY + m)
        return [[(e[2 * (c * BATTLE_H + r)], e[2 * (c * BATTLE_H + r) + 1]) for r in range(BATTLE_H)]
                for c in range(BATTLE_W)]

    def metatile(self, code: int, overlay: bool = False) -> tuple[int, int, int, int]:
        """4 BG tilemap entries (TL, TR, BL, BR) of a ground / overlay code, flips applied."""
        d, o = self.data, self.off
        if overlay:
            m = BATTLE_OVERLAY_BASE + le16(d, o["overlay_meta"] + 2 * code)
            f = le16(d, o["overlay_flip"] + 2 * code)
        else:
            m = le16(d, o["battle_meta"] + 2 * code)
            f = le16(d, o["battle_flip"] + 2 * code)
        t = [le16(d, o["metatiles"] + 8 * m + 2 * i) for i in range(4)]
        if f & 1:
            t = [t[1] | 0x4000, t[0] | 0x4000, t[3] | 0x4000, t[2] | 0x4000]
        if f & 2:
            t = [t[2] | 0x8000, t[3] | 0x8000, t[0] | 0x8000, t[1] | 0x8000]
        return tuple(t)

    def battle_tilemaps(self, m: int) -> tuple[list[int], list[int]]:
        """(ground, overlay) BG tilemaps, (2 BATTLE_W) x (2 BATTLE_H + 1) entries each, 0 = empty, laid out as the
        game's WRAM buffers $7F:0000 / $7F:20D0 without their 2-tile border."""
        w, h = 2 * BATTLE_W, 2 * BATTLE_H + 1
        ground, over = [0] * (w * h), [0] * (w * h)
        for k, (g, ov) in enumerate(self.battle_edge(m)):
            c = 2 * k + 1
            for layer, code, is_ov in ((ground, g, False), (over, ov, True)):
                if not (is_ov and code == 0xFF):
                    layer[2 * c], layer[2 * c + 1] = self.metatile(code, is_ov)[2:]
        for c, col in enumerate(self.battle_cells(m)):
            for r, (g, ov) in enumerate(col):
                y = 2 * r + (c & 1)
                for layer, code, is_ov in ((ground, g, False), (over, ov, True)):
                    if is_ov and code == 0xFF:
                        continue
                    q = self.metatile(code, is_ov)
                    layer[y * w + 2 * c], layer[y * w + 2 * c + 1] = q[0], q[1]
                    layer[(y + 1) * w + 2 * c], layer[(y + 1) * w + 2 * c + 1] = q[2], q[3]
        return ground, over

    def battle_palettes(self, pset: int = 0) -> dict[int, list[int]]:
        base = self.off["battle_palettes"] + 0x60 * pset
        return {2 + k: [le16(self.data, base + 0x20 * k + 2 * i) for i in range(16)] for k in range(3)}

    def battle_rgb(self, m: int, pset: int = 0) -> list:
        """(16 BATTLE_W) x (16 BATTLE_H + 8) RGB tuples (None = backdrop): ground, then overlay on top."""
        chars = bytes(BATTLE_CHR_SKIP) + self.entry(BATTLE_CHARS)
        pals = {p: [bgr555_rgb(c) for c in v] for p, v in self.battle_palettes(pset).items()}
        w, h = 2 * BATTLE_W, 2 * BATTLE_H + 1
        out: list = [None] * (w * 8 * h * 8)
        for layer, opaque in zip(self.battle_tilemaps(m), (True, False)):
            draw_tiles(out, layer, w, h, chars, pals, opaque)
        return out

    def siege_types(self) -> list[int]:
        """Castle -> family (0x7E, 0x83, 0x85, 0x89) of the castle-less maps 126-142, word table read by $C5:834B."""
        return [le16(self.data, self.off["siege_types"] + 2 * k) for k in range(CASTLE_COUNT)]

    def historic_battle_castles(self) -> list[int]:
        """Battle i of the 合戦 list -> castle whose attack can become it (table $C5:F4DE, read by $C5:8171)."""
        return [le16(self.data, self.off["battle_castles"] + 2 * i) for i in range(STRING_TABLES["battles"])]


def draw_tiles(out: list, tilemap: list[int], w: int, h: int, chars: bytes, pals: dict, opaque: bool) -> None:
    """Draw 8x8 BG tilemap entries into an RGB list of (w*8) x (h*8); entry 0 = nothing (overlay layer),
    colour 0 drawn only when opaque."""
    width = w * 8
    for i, e in enumerate(tilemap):
        if not e and not opaque:
            continue
        t, pal = e & 0x3FF, pals.get(e >> 10 & 7)
        if pal is None:
            continue
        px = decode_tile(chars[32 * t:32 * t + 32])
        ty, tx = divmod(i, w)
        for k, v in enumerate(px):
            if not v and not opaque:
                continue
            y, x = divmod(k, 8)
            if e & 0x8000:
                y = 7 - y
            if e & 0x4000:
                x = 7 - x
            out[(ty * 8 + y) * width + tx * 8 + x] = pal[v]


def render_cells(tilemap: list[int], w: int, h: int, chars: bytes, pals: dict) -> list:
    """16x16-tile BG (tile n = 8x8 tiles n, n+1, n+16, n+17) -> (w*16) x (h*16) RGB list."""
    small = []
    for r in range(h):
        top, bottom = [], []
        for c in range(w):
            e = tilemap[r * w + c]
            n, attr = e & 0x3FF, e & 0xFC00
            q = [n, n + 1, n + 16, n + 17]
            if e & 0x4000:
                q = [q[1], q[0], q[3], q[2]]
            if e & 0x8000:
                q = [q[2], q[3], q[0], q[1]]
            top += [attr | q[0], attr | q[1]]
            bottom += [attr | q[2], attr | q[3]]
        small += top + bottom
    out: list = [None] * (w * 16 * h * 16)
    draw_tiles(out, small, 2 * w, 2 * h, chars, pals, True)
    return out
