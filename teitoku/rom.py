"""SFC 提督の決断 (KOEI, 1992) ROM decoding.

Offsets are file offsets of the headerless 1.25 MB LoROM image ($bb:8000-$bb:FFFF = file 0x8000 * bb + addr - 0x8000).
The program is 65816 code compiled from C. The LZ decompressor ($00:9A25, tables at 0x18C8) is the shared one in
tools/koei_lz.py. Both the original release and Rev 1 are supported: Rev 1 only moves code and the LZ pointer table,
the data are byte-for-byte the same. See docs/ROM_FORMAT.md.
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Teitoku no Ketsudan (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")
LZ_TABLES = 0x18C8
ENTRY_COUNT = 433
# LZ pointer table (433 long pointers) per revision, told apart by the header version byte (0x7FDB). Rev 1 also
# moves the printf format strings that sit between code in banks $06 and $0E (the verify scripts hook printf by
# format address): original address -> Rev 1 address, each found by its bytes in both ROMs.
REVISIONS = {
    0: {"entries": 0x4F3EF, "strings": {}},
    1: {"entries": 0x4F3FB, "strings": {
        0x06FDE1: 0x06FDA8, 0x0EEEE5: 0x0EEF26, 0x0EEEF2: 0x0EEF33, 0x0EEEF5: 0x0EEF36, 0x0EEF05: 0x0EEF46,
        0x0EEF22: 0x0EEF63, 0x0EEF37: 0x0EEF78, 0x0EEFA8: 0x0EEFE9, 0x0EEFC9: 0x0EF00A, 0x0EEFE3: 0x0EF03D,
        0x0EF000: 0x0EF05A, 0x0EF01D: 0x0EF077, 0x0EF032: 0x0EF08C, 0x0EF047: 0x0EF0A1}},
}


def lorom(addr: int) -> int:
    """File offset of LoROM CPU address $bb:aaaa."""
    return (addr >> 16 & 0x7F) * 0x8000 + (addr & 0x7FFF)


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]


# ---------------------------------------------------------------- text
# Font: glyph g = 16x16 1bpp, 32 bytes at FONT + 32 g (top-left, top-right, bottom-left, bottom-right 8x8 tiles).
# Two-byte text code 0x8140 + g (big-endian); codes 0x854D-0x913F draw glyph 0, 0x9140 + k stands for 0x8200 + 0x100 k
# ($06:B5B0). One-byte codes: ASCII, and JIS X 0201 kana 0xA1-0xDF drawn as hiragana, or as katakana after ESC K
# (ESC H switches back). ESC F toggles a small set of date glyphs ("0" = 年, "1" = 月, "2" = 日 in the menus).
FONT = 0x118000
GLYPH_COUNT = 1036
DATE_GLYPHS = {"0": "年", "1": "月", "2": "日"}


def load_charset(path: str = CHARSET) -> str:
    with open(path, encoding="utf-8") as f:
        cs = "".join(line.rstrip("\n") for line in f if not line.startswith("#"))
    assert len(cs) == GLYPH_COUNT, len(cs)
    return cs


def _kana(c: int, katakana: bool) -> str:
    s = unicodedata.normalize("NFKC", bytes([c]).decode("cp932"))
    if not katakana and "ァ" <= s <= "ヶ":
        s = chr(ord(s) - 0x60)
    return s


# ---------------------------------------------------------------- initialised data
# At power-on the C runtime copies four ROM blocks to WRAM bank $7E (MVN, $00:006C); string literals stay in ROM.
# Scenario 1 is this image as it is; the other scenarios patch it (Rom.scenario_image).
DATA_SEGMENTS = [(0x101A6, 0x205A, 0x2291), (0x13567, 0x42EB, 0xB8E), (0x142E4, 0x4E79, 0xC92), (0x10000, 0x5B0B, 0x1A6)]
DATA_START, DATA_END = 0x205A, 0x5CB1

# WRAM tables ($7E:xxxx): address, record size, count
SHIPS, SHIP_SIZE, SHIP_COUNT = 0x2BA1, 22, 270
BASES, BASE_SIZE, BASE_COUNT = 0x42EB, 58, 50
FLEETS, FLEET_SIZE, FLEET_COUNT = 0x4E79, 47, 32
SIDES, SIDE_SIZE = 0x5459, 59
ADMIRALS, ADMIRAL_SIZE, ADMIRAL_COUNT = 0x54CF, 35, 40
COUNTRIES, COUNTRY_SIZE = 0x5A47, 14
SCENARIO_DATE = 0x207B          # three words: scenario patch bytes 0-2 of its "misc" section
MISC_BLOCK = 0x2AE7             # 0x60 bytes copied from the "misc" section

# Scenarios 2-9: LZ entries 383-390 ($09:F86C = pointer table + 3 * 383), applied by $0B:9A5A
SCENARIO_COUNT = 9
SCENARIO_FIRST_ENTRY = 383
SCENARIO_MENU = 0x5E80A         # "\t\t1:日米交渉決裂  S16<F>0<F>11<F>1<F> 1<F>2<F>\n..." (9 lines)


# ---------------------------------------------------------------- tables, graphics
SHIP_TYPE_NAMES = 0x1C1A3       # 16 long pointers ($03:C1A3), types 7 and 11 unused
ALLIANCE = {1: "日本", 2: "連合", 3: "中立"}
SIDE_NAMES = ["日本軍", "連合国軍"]
TRANSPORT_SPEED = 20            # top speed of a fleet with transport ships

# Faces ($0A:B2A9): face n < 27 (Japanese side) uses the 32-byte BGR555 palette FACE_PALETTES[0] + 32 k with
# k = FACE_PAL[0][n], face n >= 27 (allied side) FACE_PALETTES[1] + 32 k with k = FACE_PAL[1][n - 27]; the face is
# LZ entry n (40x48, 5x6 4bpp tiles), loaded to CGRAM row 5.
FACE_PALETTES = (0x14FEF, 0x152CF)
FACE_PAL = (0x569B9, 0x569D4)
FACE_COUNT, FACE_W, FACE_H = 54, 5, 6
# Faces that are not admirals (admiral i has face i, or i + 7 for the allied i >= 20): $0A:B2A9 maps index 100-105
# to faces 20-25 / 47-52; who they are is not named anywhere, the groups go by the uniform (推測)
OTHER_FACES = {20: "陸軍", 21: "海軍", 22: "陸軍", 23: "陸軍", 24: "飛行員", 25: "飛行員", 26: "飛行員",
               47: "陸軍", 48: "海軍", 49: "海軍", 50: "海軍", 51: "飛行員", 52: "飛行員", 53: "飛行員"}
# Ship pictures (panel of the main screen, $06:9D30): 128x32 (16x4 4bpp tiles), one per ship class c:
# LZ entry 115 + c for c < 0x34 (Japanese classes 1-0x33), c + 2 for c >= 0x34 (allied classes); palette
# SHIP_PALETTE (= FACE_PALETTES[1] + 32 * 18)
SHIP_PALETTE = 0x1550F
SHIP_PIC_W, SHIP_PIC_H = 16, 4
# Scene pictures: LZ entries 167-185, 128x48 (16x6 4bpp tiles); the fleet panel shows one instead of the flagship
# when the fleet is in port (entry 167 for the Japanese fleets at クレ, palette row 4 = SCENE_PALETTES). Which
# picture goes with which base, and the palette of the others (SCENE_PALETTES + 32 k assumed), are not decoded.
SCENE_FIRST_ENTRY, SCENE_COUNT = 167, 19
SCENE_PALETTES = 0x1558F
SCENE_W, SCENE_H = 16, 6
# World map (scenario screens, target selection): 32 x 15 tilemap words at WORLD_TILEMAP (tiles 0x2C0-0x3FC,
# palette 7), 317 4bpp tiles in an LZ stream at WORLD_TILES that is not in the entry table ($14:C515, loaded by
# $06:A112), palette WORLD_PALETTE
WORLD_TILES = 0xA4515
WORLD_TILEMAP = 0x131A7
WORLD_W, WORLD_H, WORLD_TILE0 = 32, 15, 0x2C0
WORLD_PALETTE = 0x66E8E
# Sea map (fleet movement, target selection zoom; $0A:B6xx): 32 x 16 blocks of 32x32 px (4x4 4bpp tiles), block
# (bx, by) covers map coordinates [120 bx, 120 bx + 120) x [120 by, 120 by + 120). SEA_BITS: one 32-bit row
# (MSB first) per by, set = land block; SEA_COUNT[by] = land blocks before row by. Land block k (1-196) is LZ
# entry 186 + k, open sea is entry 186 ($0A:B42A). Same palette as the world map.
SEA_BITS = 0x569EF
SEA_COUNT = 0x56A2F
SEA_W, SEA_H, SEA_BLOCK, SEA_FIRST_ENTRY = 32, 16, 120, 186


def decode_tile(raw: bytes, o: int = 0) -> list[list[int]]:
    """8x8 SNES 4bpp tile -> rows of colour indices."""
    return [[sum((raw[o + (k >> 1) * 16 + 2 * y + (k & 1)] >> (7 - x) & 1) << k for k in range(4)) for x in range(8)]
            for y in range(8)]


def tiles_pixels(raw: bytes, w: int, h: int) -> list[int]:
    """w x h tiles stored row by row -> (8 w) x (8 h) colour indices."""
    out = [0] * (64 * w * h)
    for t in range(w * h):
        for y, row in enumerate(decode_tile(raw, 32 * t)):
            for x, c in enumerate(row):
                out[((t // w) * 8 + y) * 8 * w + (t % w) * 8 + x] = c
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return ((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31)


def le16(raw, o: int) -> int:
    return raw[o] | raw[o + 1] << 8


def le32(raw, o: int) -> int:
    return int.from_bytes(raw[o:o + 4], "little")


class Tables:
    """Part of Rom: the WRAM tables of a scenario as dicts, faces, pictures, maps."""

    def palette(self, o: int) -> list[int]:
        return [le16(self.data, o + 2 * k) for k in range(16)]

    def type_names(self) -> list[str]:
        out = []
        for t in range(16):
            p = self.ptr(SHIP_TYPE_NAMES + 3 * t)
            out.append(self.string(p) if p else "")
        return out

    def scenarios(self) -> list[dict]:
        lines = self.text(self.data, SCENARIO_MENU).split("\n")
        out = []
        for sc, line in enumerate(lines, 1):
            num_title, date = line.strip("\t").split(None, 1)
            img = self.scenario_image(sc)
            y, m, d = (le16(img, SCENARIO_DATE + 2 * k) for k in range(3))
            out.append({"id": sc, "title": num_title.split(":", 1)[1], "date_text": date.replace(" ", ""),
                        "date": f"{1925 + y}-{m:02d}-{d:02d}", "showa": y})
        return out

    def elapsed_months(self, sc: int) -> int:
        """Months from 1941-11 (scenario 1) to the start of scenario sc. Ship +11 (the month of completion of a
        ship under construction, counted the same way) is lowered by this at the start of a game: ships with
        +14 bit 1 and +11 <= elapsed are already complete."""
        img = self.scenario_image(sc)
        return le16(img, SCENARIO_DATE) * 12 + le16(img, SCENARIO_DATE + 2) - (16 * 12 + 11)

    def ships(self, sc: int = 1) -> list[dict]:
        img, names = self.scenario_image(sc), self.type_names()
        elapsed = self.elapsed_months(sc)
        out = []
        for i in range(SHIP_COUNT):
            b = img[SHIPS + SHIP_SIZE * i:SHIPS + SHIP_SIZE * (i + 1)]
            name, _, reading = self.string(int.from_bytes(b[0:3], "little")).partition(" ")
            out.append({
                "id": i, "name": name, "reading": reading, "side": b[0x15] & 1, "type": b[3], "type_name": names[b[3]],
                "fleet": b[4], "anti_ship": b[5], "anti_air": b[6], "armor": b[7], "speed": b[8], "capacity": b[9],
                "fighters": b[0x0A], "attackers": b[0x0B], "scouts": b[0x0C], "troops": b[0x0D], "unk_0e": b[0x0E],
                "unk_0f": b[0x0F], "unk_10": b[0x10], "complete_month": b[0x11], "unk_12": b[0x12],
                "class": b[0x13], "building": int(b[0x14] >> 1 & 1 and b[0x11] > elapsed), "sunk": b[0x15] >> 2 & 1,
                "status": b[0x14], "flags": b[0x15]})
        return out

    def bases(self, sc: int = 1) -> list[dict]:
        img = self.scenario_image(sc)
        out = []
        for i in range(BASE_COUNT):
            b = img[BASES + BASE_SIZE * i:BASES + BASE_SIZE * (i + 1)]
            out.append({
                "id": i, "name": self.string(int.from_bytes(b[1:4], "little")), "code": bytes(b[4:6]).decode("ascii"),
                "owner": b[0x38] & 1, "armament_max": (b[7] >> 4) * 10, "durability_max": (b[7] & 15) * 10,
                "armament": b[8], "durability": b[9], "fighters": le16(b, 0x0A), "attackers": le16(b, 0x0C),
                "scouts": le16(b, 0x0E), "twin_engine": le16(b, 0x10), "rockets": le16(b, 0x12),
                "large_planes": le16(b, 0x14), "fuel": le32(b, 0x16), "materials": le16(b, 0x1A),
                "troops": le16(b, 0x1C), "x": le16(b, 0x1E), "y": le16(b, 0x20), "unk_22": b[0x22], "iron": b[0x23],
                "oil": b[0x24], "population": b[0x25], "industry": b[0x26], "troop_ships": b[0x27],
                "fuel_ships": b[0x28], "friendship": b[0x29], "hq": int(b[0x37] == 2), "flags": le16(b, 0x38),
                "raw": bytes(b).hex()})
        return out

    def fleets(self, sc: int = 1) -> list[dict]:
        img = self.scenario_image(sc)
        out = []
        for i in range(FLEET_COUNT):
            b = img[FLEETS + FLEET_SIZE * i:FLEETS + FLEET_SIZE * (i + 1)]
            if le16(b, 0) & 0x8000:
                continue
            out.append({
                "id": i, "side": i // 16, "number": b[0x0A], "x": le16(b, 0), "y": le16(b, 2), "dest_x": le16(b, 4),
                "dest_y": le16(b, 6), "base": b[8] - 1, "admiral": b[0x0B] if b[0x0B] != 0xFF else -1,
                "fuel": le32(b, 0x0C), "morale": b[0x11], "fatigue": b[0x12], "fuel_ships": b[0x17],
                "troop_ships": [v & 0x7F for v in b[0x18:0x1C] if v & 0x80],
                "flagship": (le16(b, 0x14) - SHIPS) // SHIP_SIZE, "raw": bytes(b).hex()})
        return out

    def sides(self, sc: int = 1) -> list[dict]:
        img = self.scenario_image(sc)
        out = []
        for i in range(2):
            b = img[SIDES + SIDE_SIZE * i:SIDES + SIDE_SIZE * (i + 1)]
            out.append({"id": i, "name": self.text(bytes(b), 1), "hq": b[0x35] - 1, "raw": bytes(b).hex()})
        return out

    def admirals(self, sc: int = 1) -> list[dict]:
        img = self.scenario_image(sc)
        out = []
        for i in range(ADMIRAL_COUNT):
            b = img[ADMIRALS + ADMIRAL_SIZE * i:ADMIRALS + ADMIRAL_SIZE * (i + 1)]
            f = b[0x22]
            out.append({"id": i, "name": self.text(bytes(b)), "side": i // 20, "face": self.admiral_face(i),
                        "fleet": f & 0x1F, "absent": f >> 7, "foreign": f >> 5 & 3, "flags": f})
        return out

    def countries(self, sc: int = 1) -> list[dict]:
        img = self.scenario_image(sc)
        out, d = [], COUNTRIES
        while any(img[d:d + 3]):
            b = img[d:d + COUNTRY_SIZE]
            out.append({"id": len(out), "name": self.string(int.from_bytes(b[0:3], "little")), "alliance": b[3],
                        "to_japan": b[4], "to_allies": b[5], "unk_6": b[6], "unk_7": b[7],
                        "values": list(b[8:0x0D]), "flags": b[0x0D]})
            d += COUNTRY_SIZE
        return out

    # --- faces
    @staticmethod
    def admiral_face(i: int) -> int:
        """Face of admiral i ($0A:B2A9 with side i // 20 and index i)."""
        return i if i < 20 else i + 7

    def face_palette_number(self, n: int) -> int:
        return self.data[FACE_PAL[0] + n] if n < 27 else self.data[FACE_PAL[1] + n - 27]

    def face_palette(self, n: int) -> list[int]:
        return self.palette(FACE_PALETTES[n >= 27] + 32 * self.face_palette_number(n))

    def face_pixels(self, n: int) -> list[int]:
        return tiles_pixels(self.entry(n), FACE_W, FACE_H)

    def face_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette(n)]
        return [pal[c] for c in self.face_pixels(n)]

    # --- ship pictures
    @staticmethod
    def ship_picture_entry(ship_class: int) -> int:
        return 115 + ship_class if ship_class < 0x34 else ship_class + 2

    def ship_picture_rgb(self, ship_class: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.palette(SHIP_PALETTE)]
        return [pal[c] for c in tiles_pixels(self.entry(self.ship_picture_entry(ship_class)), SHIP_PIC_W, SHIP_PIC_H)]

    # --- maps
    def world_tiles(self) -> bytes:
        return koei_lz.decompress(self.data, WORLD_TILES, LZ_TABLES)[0]

    def world_tilemap(self) -> bytes:
        return self.data[WORLD_TILEMAP:WORLD_TILEMAP + 2 * WORLD_W * WORLD_H]

    def world_rgb(self) -> list[tuple[int, int, int]]:
        tiles, tm = self.world_tiles(), self.world_tilemap()
        pal = [bgr555_rgb(c) for c in self.palette(WORLD_PALETTE)]
        out = [(0, 0, 0)] * (WORLD_W * 8 * WORLD_H * 8)
        for ty in range(WORLD_H):
            for tx in range(WORLD_W):
                e = le16(tm, 2 * (ty * WORLD_W + tx))
                for y, row in enumerate(decode_tile(tiles, 32 * ((e & 0x3FF) - WORLD_TILE0))):
                    yy = 7 - y if e & 0x8000 else y
                    for x, c in enumerate(row):
                        xx = 7 - x if e & 0x4000 else x
                        out[(ty * 8 + yy) * WORLD_W * 8 + tx * 8 + xx] = pal[c]
        return out

    def sea_block(self, bx: int, by: int) -> int:
        """Land block number of block (bx, by), 0 = open sea ($0A:B42A)."""
        row = self.data[SEA_BITS + 4 * by:SEA_BITS + 4 * by + 4]
        if not row[bx >> 3] & 0x80 >> (bx & 7):
            return 0
        n = sum(v.bit_count() for v in row[:bx >> 3]) + (row[bx >> 3] >> (7 - (bx & 7))).bit_count()
        return le16(self.data, SEA_COUNT + 2 * by) + n

    def sea_rgb(self) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.palette(WORLD_PALETTE)]
        w = SEA_W * 32
        out = [(0, 0, 0)] * (w * SEA_H * 32)
        for by in range(SEA_H):
            for bx in range(SEA_W):
                px = tiles_pixels(self.entry(SEA_FIRST_ENTRY + self.sea_block(bx, by)), 4, 4)
                for k, c in enumerate(px):
                    out[(by * 32 + k // 32) * w + bx * 32 + k % 32] = pal[c]
        return out


class Rom(Tables):
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        assert koei_lz.find_tables(self.data) == LZ_TABLES
        self.rev = self.data[0x7FDB]  # header version byte
        self.off = REVISIONS[self.rev]
        self.charset = load_charset()
        self._cache: dict[int, bytes] = {}

    def string_addr(self, addr: int) -> int:
        """Address of a format string in this revision, given its address in the original version."""
        return self.off["strings"].get(addr, addr)

    def lua_string_map(self, addrs: list[int]) -> str:
        """Lua table body {[address in this ROM] = original address, ...} for printf hooks."""
        return ",".join(f"[{self.string_addr(a)}]={a}" for a in addrs)

    # --- generic
    def entry(self, i: int) -> bytes:
        if i not in self._cache:
            t = self.off["entries"] + 3 * i
            p = lorom(int.from_bytes(self.data[t:t + 3], "little"))
            self._cache[i] = koei_lz.decompress(self.data, p, LZ_TABLES)[0]
        return self._cache[i]

    def ptr(self, o: int) -> int:
        return int.from_bytes(self.data[o:o + 3], "little")

    def text(self, raw: bytes, i: int = 0) -> str:
        """Game string -> str, up to NUL. Unknown control bytes become [xx]."""
        out, kata, date = [], False, False
        while i < len(raw) and raw[i]:
            c = raw[i]
            if 0x81 <= c <= 0x9F or c >= 0xE0:
                code = c << 8 | raw[i + 1]
                if code >= 0x9140:
                    code = 0x8200 + ((code - 0x9140) << 8)
                g = code - 0x8140 if code <= 0x854C else 0
                out.append(self.charset[g])
                i += 2
                continue
            if c == 0x1B:
                k = chr(raw[i + 1])
                if k in "KH":
                    kata = k == "K"
                elif k == "F":
                    date = not date
                else:
                    out.append(f"[1b{raw[i + 1]:02x}]")
                i += 2
                continue
            if date and chr(c) in DATE_GLYPHS:
                out.append(DATE_GLYPHS[chr(c)])
            elif 0xA1 <= c <= 0xDF:
                out.append(_kana(c, kata))
            elif 0x20 <= c < 0x7F:
                out.append(chr(c))
            elif c == 0x0A:
                out.append("\n")
            elif c == 0x09:
                out.append("\t")
            else:
                out.append(f"[{c:02x}]")
            i += 1
        return unicodedata.normalize("NFC", "".join(out))  # kana + combining (han)dakuten

    def string(self, addr: int) -> str:
        """String at CPU address addr (bank $02 strings of the data tables)."""
        return self.text(self.data, lorom(addr))

    def glyph(self, g: int) -> list[list[int]]:
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        return [[raw[(y // 8 * 2 + x // 8) * 8 + y % 8] >> (7 - x % 8) & 1 for x in range(16)] for y in range(16)]

    # --- WRAM images
    def data_image(self) -> bytearray:
        """WRAM bank $7E after power-on (only DATA_START-DATA_END is filled)."""
        img = bytearray(0x10000)
        for src, dst, n in DATA_SEGMENTS:
            img[dst:dst + n] = self.data[src:src + n]
        return img

    def scenario_image(self, sc: int) -> bytearray:
        """WRAM bank $7E right after scenario sc (1-9) is loaded ($0B:9A5A)."""
        img = self.data_image()
        if sc == 1:
            return img
        s = self.entry(SCENARIO_FIRST_ENTRY + sc - 2)
        p = 0
        w = lambda o, v: img.__setitem__(slice(o, o + 2), (v & 0xFFFF).to_bytes(2, "little"))
        rw = lambda b, o: b[o] | b[o + 1] << 8

        def lptr(o: int, base: int, size: int, idx: int) -> None:  # 24-bit pointer base + idx * size in bank $7E
            v = base + idx * size
            img[o:o + 2] = (v & 0xFFFF).to_bytes(2, "little")
            img[o + 2] = 0x7E + (v >> 16)

        for i in range(SHIP_COUNT):  # ships: 10 bytes each
            r, d = s[p:p + 10], SHIPS + SHIP_SIZE * i
            img[d + 4] = r[0]
            img[d + 9:d + 16] = r[1:8]
            img[d + 0x14] = r[8]
            img[d + 0x15] = img[d + 0x15] & 0x3B | r[9]
            p += 10
        for i in range(BASE_COUNT):  # bases: 35 bytes each
            r, d = s[p:p + 35], BASES + BASE_SIZE * i
            img[d + 7:d + 10] = r[0:3]
            img[d + 0x0A:d + 0x1E] = r[3:0x17]
            img[d + 0x22] = r[0x17]
            img[d + 0x27:d + 0x2A] = r[0x18:0x1B]
            if img[d + 0x25] == 0:
                img[d + 0x29] = 0x32
            img[d + 0x31:d + 0x37] = r[0x1B:0x21]
            w(d + 0x38, rw(img, d + 0x38) & 0x3800 | rw(r, 0x21))
            p += 35
        for i in range(FLEET_COUNT):  # fleets: 27 bytes each
            r, d = s[p:p + 27], FLEETS + FLEET_SIZE * i
            img[d:d + 2] = r[0:2]
            if rw(r, 0) & 0x8000:  # unused fleet
                img[d + 2:d + 8] = b"\xff" * 6
                img[d + 8] = img[d + 9] = 0
                img[d + 0x0B] = 0xFF
                for o in (0x0C, 0x0E, 0x15):
                    w(d + o, 0)
                for o in (0x11, 0x12, 0x14, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x2C):
                    img[d + o] = 0
                w(d + 0x2D, 0)
            else:
                img[d + 2:d + 10] = r[2:10]
                if r[0x0A]:
                    img[d + 0x0B] = (r[0x0A] + i // 16 * 20 - 1) & 0xFF
                img[d + 0x0C:d + 0x10] = r[0x0B:0x0F]
                img[d + 0x11] = r[0x0F]
                img[d + 0x12] = r[0x10]
                lptr(d + 0x14, SHIPS, SHIP_SIZE, rw(r, 0x11))
                img[d + 0x17:d + 0x1C] = r[0x13:0x18]
                img[d + 0x2C] = r[0x18]
                img[d + 0x2D:d + 0x2F] = r[0x19:0x1B]
            p += 27
        for i in range(2):  # sides: 46 bytes each
            r, d = s[p:p + 46], SIDES + SIDE_SIZE * i
            img[d + 8:d + 0x22] = r[0:0x1A]
            img[d + 0x22] = r[0x1A]
            img[d + 0x23:d + 0x25] = r[0x1B:0x1D]
            img[d + 0x25:d + 0x2C] = r[0x1D:0x24]
            for k, o in enumerate((0x2C, 0x2F, 0x32)):
                lptr(d + o, BASES, BASE_SIZE, rw(r, 0x24 + 2 * k))
            img[d + 0x35] = r[0x2A]
            img[d + 0x36:d + 0x38] = r[0x2B:0x2D]
            img[d + 0x3A] = r[0x2D]
            p += 46
        r = s[p:p + 0x8B]  # misc: date, admiral flags, a 0x60-byte block
        for k in range(3):
            w(SCENARIO_DATE + 2 * k, r[k])
        for i in range(ADMIRAL_COUNT):
            img[ADMIRALS + ADMIRAL_SIZE * i + 0x22] |= r[3 + i]
        img[MISC_BLOCK:MISC_BLOCK + 0x60] = r[0x2B:0x8B]
        p += 0x8B
        d = COUNTRIES
        while any(img[d:d + 3]):  # countries: 11 bytes each, up to the record whose name pointer is 0
            r = s[p:p + 11]
            img[d + 3:d + 9] = r[0:6]
            img[d + 8] = min(img[d + 8], 0x63)
            for k in range(4):
                img[d + 9 + k] = min(r[6 + k], 0x63)
            if img[d + 0x0B] >= 0x50:
                img[d + 0x0D] |= 1
            if img[d + 0x0B] >= 0x5F:
                img[d + 0x0D] |= 2
            if img[d + 0x0B] >= 0x50 and img[d + 0x0C] >= 0x50:
                img[d + 0x0D] |= 8
            p += 11
            d += COUNTRY_SIZE
        for side in range(2):  # each side's headquarters base: +0x37 = 2
            b = img[SIDES + SIDE_SIZE * side + 0x35] - 1
            img[BASES + BASE_SIZE * b + 0x37] = 2
        return img
