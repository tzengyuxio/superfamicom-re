"""SFC 横山光輝 三国志 (Angel, 1992) ROM decoding.

The ROM is a headerless 1 MB LoROM image: CPU $bb:8000-$FFFF = file 0x8000 bb + (addr - 0x8000). There is no KOEI
LZ and no Shift-JIS: text is a list of 16-bit codes drawn by $00:8D60 (data/charset.txt), graphics are packed with
an LZSS variant ($01:F8FE, see lz()). Two revisions exist (Rev 0, Rev 1); some tables moved by 4 bytes in Rev 1, so
their addresses are read from the program (Rom._find). See docs/ROM_FORMAT.md.
"""
import os
import re
import struct
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_ROM = os.path.join(REPO, "roms", "Yokoyama Mitsuteru Sangokushi (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")
REV1_CHARS = {0x342: "褚"}  # Rev 1 redrew glyph 0x342 (緒 -> 褚: 許緒 -> 許褚)

# Fonts ($00:8D60): code 0x200-0x5FF is a 16x16 glyph at FONT16 + 32 (code - 0x200) (8x8 tiles TL BL TR BR, one
# byte per row); 0x100-0x1FF an 8x16 glyph at FONT8 + 16 (code - 0x100); codes below 0xF1 print as code + 0x10.
# Codes 0x600 and up would read $04:0000- (not ROM): charset.txt lists them as □.
FONT16, FONT16_COUNT = 0x038000, 0x400
FONT8 = 0x048800
TEXT_NEWLINE, TEXT_END = 0x000A, 0x0000
# Control codes (16-bit, 0xF1-0xF9): what $00:8E67 prints for them
CONTROL = {0xF1: "{武将:$0448}", 0xF2: "{君主:$6F}", 0xF3: "{武将:$75}", 0xF4: "{武将:$87}", 0xF5: "{数:$65}",
           0xF6: "{国:$6D}", 0xF7: "{数4:$65}", 0xF8: "{武将:$89}", 0xF9: "{数4:$67}"}

PERSON_COUNT = 224
NAMES = 0x04B080                 # 224 x 8: surname, middle (0x200 = none), given name, reading pointer ($04:xxxx)
PERSON_SIZE = 14                 # ROM record; WRAM record is 22 bytes at PERSON_WRAM (4 bytes before, 4 after)
PERSON_WRAM, PERSON_WRAM_SIZE = 0x0800, 22
PLACE_SIZE = 5
COUNTRY_COUNT, COUNTRY_SIZE = 31, 16
COUNTRY_WRAM, COUNTRY_WRAM_SIZE = 0x1B40, 21   # 0, the ROM record, 4 zero bytes
FACTION_COUNT = 15
FACTION_WRAM, FACTION_WRAM_SIZE = 0x1DCB, 5     # flag (FF = no ruler), ruler, FF, 0, 0
SCENARIO_YEARS = [189, 219]                     # $01:D4A9: start year 0xBD / 0xDB

# Person record (ROM, 14 bytes). The WRAM copy adds before it: +0 faction | 0x80 (0xC0 = not in the game),
# +1 country | 0x80, +2 0, +3 レベル = 経験値 // 100 + 1; and 4 zero bytes after.
PERSON_FIELDS = [  # (name, offset, size)
    ("体力", 0, 1), ("攻撃力", 1, 1), ("兵法力", 2, 1), ("政治力", 3, 1), ("忠誠度", 4, 1), ("人徳", 5, 1),
    ("経験値", 6, 2), ("統率力", 8, 1), ("兵数", 9, 2), ("士気", 11, 1), ("武器", 12, 1), ("機動力", 13, 1),
]
# Country record (ROM, 16 bytes)
COUNTRY_FIELDS = [
    ("勢力", 0, 1), ("太守", 1, 1), ("金", 2, 2), ("米", 4, 2), ("民", 6, 2), ("収穫高", 8, 2), ("産業値", 10, 2),
    ("統治度", 12, 1), ("防災値", 13, 1), ("税率", 14, 1), ("城塞値", 15, 1),
]
DIFFICULTY_GOLD_FOOD = {0: 160}  # difficulty 1 ($044A = 0): 金 and 米 x 160 / 100 at the start ($01:D5E1)

# Placement record (5 bytes per person and scenario): kind, country, ref, year, 0
PLACE_KINDS = {0: "仕官", 1: "在野", 2: "親族", 3: "勢力", 4: "推挙", 5: "登用", 0xFF: "不在"}

# Faces: 224 x 11 part numbers at FACE_PARTS (Rev 0; = person number), copied to $013B-$0145 by $00:8B4D, which
# builds 16x16 sprite tiles in a 16-tile-wide buffer ($7E:8000). Part k: (bank:base, bytes per part, bytes per row
# copied, first sprite tile, rows (each 2 tile rows), copies). FF = none (except parts 0-2, 4, 8).
FACE_SLOTS = [  # (source CPU address, step, width in bytes per tile row, first 8x8 tile in the buffer)
    (0x08E900, 0x100, 0x80, 0x00),    # 0 $013B -> sprite tiles 00-02
    (0x088000, 0x300, 0x180, 0x04),   # 1 $013C -> 04-0E
    (0x0B8000, 0x200, 0x100, 0x40),   # 2 $013D -> 40-46
    (0x0AC400, 0x100, 0x80, 0x60),    # 3 $013E -> 60-62
    (0x0BCA00, 0x200, 0x100, 0x48),   # 4 $013F -> 48-4E
    (0x0A8000, 0x100, 0x80, 0x2C),    # 5 $0140 -> 2C-2E
    (0x09CC00, 0x100, 0x80, 0x28),    # 6 $0141 -> 28-2A
    (0x098000, 0x100, 0x80, 0x24),    # 7 $0142 -> 24-26
    (0x0BDE00, 0x80, 0x40, 0x20),     # 8 $0143 -> 20
    (0x0BF200, 0x80, 0x40, 0x22),     # 9 $0144 -> 22
    (0x08F300, 0x80, 0x40, 0x64),     # 10 $0145 -> 64-66 (0x80 bytes at 0x40-byte rows, copied twice: 64, 66)
]
FACE_OPTIONAL = {3, 5, 6, 7, 9, 10}
META_TABLE = 0x018A08            # metasprites: bank-$01 pointers; record = count, count x (dx, dy, tile, attr)
FACE_META = 0                    # the face layout (48 x 64, 32 sprites, outer columns mirrored)
FACE_EXTRA = {0x21: 0x150, 0x4A: 0x151, 0x91: 0x152, 0xB8: 0x153}  # $01:8948: extra sprites for 4 faces
FACE_W, FACE_H = 48, 64
FACE_SKIN = 0x05B033             # OBJ palettes 0-1 (64 bytes); then palette 1 = FACE_PALETTES + 32 face

# Strategic map (mode 7, $05:8000): bank $19 ($19:8000-$FFFF) is copied as is to $7E:8000 and then to VRAM 0:
# interleaved words, low byte = 128 x 128 tilemap, high byte = 256 8bpp tiles (8 x 8, one byte per pixel). It is
# shown at 1/4 scale (matrix 0x400) and 1:1 when zoomed. $05:8039 puts a city marker on every country and $05:8097
# a castle frame around it; $05:8126 adds marching armies (none at the start).
MAP_BANK, MAP_TILES = 0x198000, 128
MAP_MARKER_FRAMES = 0x058102          # 3 x 12 tile numbers: 城塞値 < 0x21 / < 0x42 / else
MAP_FRAME_OFFSETS = [(-1, -1), (0, -1), (1, -1), (2, -1), (-1, 0), (2, 0), (-1, 1), (2, 1), (-1, 2), (0, 2), (1, 2),
                     (2, 2)]          # (column, row) of the frame tiles from the marker's top-left tile
MAP_PALETTE = 0x05AF33                # 256 colours; then colours 0x20-0x3F from MAP_MONTH + 64 month ($0127)
MAP_MONTH = 0x05B1B3
MAP_MONTH_SMALL = 0x05B4B3            # colours 0x40-0x4F at 1/4 scale (+ 32 month); 0xF0-0xFF from $05:8243
MAP_MONTH_ZOOM = 0x05B633             # colours 0x40-0x4F at 1:1 (+ 32 month); 0xF0-0xFF = colour 0x0F
MAP_SMALL_TOP = 0x058243              # 16 colours 0xF0-0xFF at 1/4 scale
# The window palette ($02:CB1B in Rev 0, Rom.window_palette_at): $02:C9F2 puts these 16 colours in rows 5, 14 and
# 15 (the map's colours 0x50-0x5E and 0xF0-0xFF on screen); colours 0x50 / 0xF0 then blink
WINDOW_ROWS = (5, 14, 15)

# Terrain: 64 x 64 cells of 16 x 16 map pixels (= the 4-pixel units of rom.Rom.position), index 64 y + x
# ($01:CD25 / $01:CD42); names ($00:BCC8, 2 codes each) and movement class ($01:CD6D in Rev 0,
# Rom.terrain_move_at; >= 0x80 = impassable)
TERRAIN, TERRAIN_SIZE = 0x1DD8CE, 64
TERRAIN_NAMES = 0x189D86
TERRAIN_KINDS = 8


def off(addr: int) -> int:
    """LoROM CPU address -> file offset."""
    return (addr >> 16 & 0x7F) * 0x8000 + (addr & 0x7FFF)


def cpu(o: int) -> int:
    return (o // 0x8000) << 16 | 0x8000 + o % 0x8000


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]


def load_charset(path: str = CHARSET) -> dict[int, str]:
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            first, chars = line.rstrip("\n").split("\t")
            for k, c in enumerate(chars):
                out[int(first, 16) + k] = c
    return out


def lz(data: bytes, addr: int) -> tuple[bytes, int]:
    """Decompress the stream at CPU address addr ($01:F8FE): LE16 output size, then flag bytes read LSB first;
    1 = literal byte, 0 = LE16 word w: copy (w & 15) + 3 bytes from distance w >> 4 back (positions before the
    start read as 0). Returns (data, compressed length)."""
    o = start = off(addr)
    size = le16(data, o)
    o += 2
    out = bytearray()
    bits = n = 0
    while len(out) < size:
        if n == 0:
            bits, n = data[o], 8
            o += 1
        n -= 1
        flag, bits = bits & 1, bits >> 1
        if flag:
            out.append(data[o])
            o += 1
        else:
            w = le16(data, o)
            o += 2
            dist = w >> 4
            for _ in range((w & 15) + 3):
                p = len(out) - dist
                out.append(out[p] if p >= 0 else 0)
    return bytes(out[:size]), o - start


def decode_tile4(raw: bytes) -> list[int]:
    """One 4bpp SNES tile (32 bytes) -> 64 colour numbers, row-major."""
    out = []
    for y in range(8):
        p0, p1, p2, p3 = raw[2 * y], raw[2 * y + 1], raw[16 + 2 * y], raw[17 + 2 * y]
        for x in range(7, -1, -1):
            out.append((p0 >> x & 1) | (p1 >> x & 1) << 1 | (p2 >> x & 1) << 2 | (p3 >> x & 1) << 3)
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return tuple((c >> s & 31) << 3 | (c >> s & 31) >> 2 for s in (0, 5, 10))


def palette(raw: bytes) -> list[tuple[int, int, int]]:
    return [bgr555_rgb(le16(raw, 2 * i)) for i in range(len(raw) // 2)]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.revision = self.data[0x7FDB]
        self.charset = load_charset()
        if self.revision == 1:
            self.charset.update(REV1_CHARS)
        self._find()

    # --- table addresses, read from the program (Rev 1 moved several tables by 4 bytes) ---
    def _match(self, pattern: bytes, group: int = 1) -> list[int]:
        return [int.from_bytes(m.group(group), "little") for m in re.finditer(pattern, self.data, re.DOTALL)]

    def _find(self) -> None:
        d = self.data
        # Scenario loader $01:D4A9: LDX #rev0 ; LDA $011F ; BEQ +3 ; LDX #rev1 (persons, placement, countries, factions)
        pairs = [(int.from_bytes(m.group(1), "little"), int.from_bytes(m.group(2), "little"))
                 for m in re.finditer(rb"\xa2(..)\xad\x1f\x01\xf0\x03\xa2(..)", d[0xD400:0xD600], re.DOTALL)]
        years, persons, places, countries, factions = pairs[:5]
        assert years == (SCENARIO_YEARS[0], SCENARIO_YEARS[1]), years
        self.persons_at = [0x040000 | a for a in persons]
        self.places_at = [0x040000 | a for a in places]
        self.countries_at = [0x040000 | a for a in countries]
        self.factions_at = [0x040000 | a for a in factions]
        self.country_names_at = self._match(rb"\xa5\x6d\x0a\x0a\xaa\xbf(...)")[0]       # $00:8EB8
        self.country_readings_at = self.country_names_at + 4 * COUNTRY_COUNT
        self.positions_at = self._match(rb"\xa2\x00\xbf(...)\x38\xe5\x00")[0]          # $01:CACB
        self.face_parts_at = 0x040000 | self._match(rb"\x18\x69(..)\xaa\xa0\x3b\x01")[0]  # $00:8B74
        self.face_palettes_at = 0x040000 | self._match(rb"\x18\x69(..)\xaa\xa0\x20\x06")[0]  # $00:8A96
        self.terrain_move_at = 0x010000 | self._match(rb"\xbf\xce\xd8\x1d\x29\xff\x00\xaa\xbf(..)")[0]  # $01:CD61
        self.window_palette_at = 0x020000 | self._match(rb"\xbd(..)\x9d\xa0\x05\x9d\xc0\x06")[0]      # $02:C9F5
        # loader: LDA $044A ; CMP #2 ; BNE (the difficulty-3 change; Rev 0 $01:D612), the one in the loader
        self.loader_done = cpu(next(m.start() for m in re.finditer(rb"\xad\x4a\x04\xc9\x02\x00\xd0", d)
                                    if 0xD400 <= m.start() < 0xD800))
        # LZSS decompressor (Rev 0 $01:F8FE) and its PLP before the RTL (Rev 0 $01:F99F)
        self.lz_entry = cpu(d.index(b"\x85\xf7\x86\xf9\x08\x8b\xe2\x20"))
        self.lz_return = cpu(re.search(rb"\x7a\xe4\xfd\x90.\xab\x28\x6b", d, re.DOTALL).start() + 6)
        assert self._match(rb"\xbf(...)\x85\x00\xbf..\x04\x85\x03\xbf..\x04\x85\x06")[0] == NAMES

    def u8(self, addr: int) -> int:
        return self.data[off(addr)]

    def u16(self, addr: int) -> int:
        return le16(self.data, off(addr))

    def raw(self, addr: int, n: int) -> bytes:
        return self.data[off(addr):off(addr) + n]

    # --- text ---
    def char(self, code: int) -> str:
        if code in CONTROL:
            return CONTROL[code]
        return self.charset.get(code, f"[{code:X}]")

    def text(self, codes) -> str:
        return "".join("\n" if c == TEXT_NEWLINE else self.char(c) for c in codes)

    def codes_at(self, addr: int, limit: int = 4000) -> list[int]:
        out = []
        while len(out) < limit:
            c = self.u16(addr + 2 * len(out))
            if c == TEXT_END:
                break
            out.append(c)
        return out

    def glyph16(self, code: int) -> list[list[int]]:
        """16x16 bitmap (rows of 0/1) of a code >= 0x200."""
        raw = self.raw(FONT16 + 32 * (code - 0x200), 32)
        rows = [[0] * 16 for _ in range(16)]
        for t, (tx, ty) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
            for r in range(8):
                b = raw[8 * t + r]
                for c in range(8):
                    rows[8 * ty + r][8 * tx + c] = b >> (7 - c) & 1
        return rows

    def glyph8(self, code: int) -> list[list[int]]:
        raw = self.raw(FONT8 + 16 * (code - 0x100), 16)
        return [[b >> (7 - c) & 1 for c in range(8)] for b in raw]

    # --- persons ---
    def name_codes(self, p: int) -> list[int]:
        a, b, c, _ = struct.unpack_from("<4H", self.data, off(NAMES + 8 * p))
        return [a] + ([b] if b != 0x200 else []) + [c]

    def name(self, p: int) -> str:
        return self.text(self.name_codes(p))

    def reading(self, p: int) -> str:
        return self.text(self.codes_at(0x040000 | self.u16(NAMES + 8 * p + 6)))

    def person_raw(self, scenario: int, p: int) -> bytes:
        return self.raw(self.persons_at[scenario] + PERSON_SIZE * p, PERSON_SIZE)

    def person(self, scenario: int, p: int) -> dict:
        return decode_person(self.person_raw(scenario, p))

    def place(self, scenario: int, p: int) -> bytes:
        return self.raw(self.places_at[scenario] + PLACE_SIZE * p, PLACE_SIZE)

    # --- countries, factions ---
    def country_name(self, c: int) -> str:
        return self.text([self.u16(self.country_names_at + 4 * c), self.u16(self.country_names_at + 4 * c + 2)])

    def country_reading(self, c: int) -> str:
        return self.text(self.codes_at(0x040000 | self.u16(self.country_readings_at + 2 * c)))

    def country_raw(self, scenario: int, c: int) -> bytes:
        return self.raw(self.countries_at[scenario] + COUNTRY_SIZE * c, COUNTRY_SIZE)

    def country(self, scenario: int, c: int) -> dict:
        return decode_fields(self.country_raw(scenario, c), COUNTRY_FIELDS)

    def position(self, c: int) -> tuple[int, int]:
        """Map position of country c in 4-pixel units of the 256-pixel-wide (shrunk) map (cursor $0113 >> 4)."""
        return self.u8(self.positions_at + 2 * c), self.u8(self.positions_at + 2 * c + 1)

    def rulers(self, scenario: int) -> list[int]:
        """Faction f -> ruler person number (0xFF = no faction)."""
        return list(self.raw(self.factions_at[scenario], FACTION_COUNT))

    # --- scenario start state, as the loader $01:D4A9 builds it ---
    def scenario_wram(self, scenario: int, difficulty: int = 0) -> dict[int, bytes]:
        """WRAM blocks {address: bytes} of persons, countries and factions right after the loader, before the
        difficulty-3 change to the other rulers (Rom.loader_done)."""
        countries = bytearray()
        for c in range(COUNTRY_COUNT):
            rec = bytearray(self.country_raw(scenario, c))
            if difficulty == 0:
                for i in (2, 4):
                    v = le16(rec, i) * DIFFICULTY_GOLD_FOOD[0] // 100
                    rec[i:i + 2] = (v & 0xFFFF).to_bytes(2, "little")
            countries += b"\0" + rec + b"\0" * 4
        countries = countries[:COUNTRY_COUNT * COUNTRY_WRAM_SIZE]
        persons = bytearray()
        for p in range(PERSON_COUNT):
            rec = self.person_raw(scenario, p)
            kind, country = self.place(scenario, p)[:2]
            head = bytearray(4)
            if kind == 0:
                head[1] = country | 0x80
                head[0] = self.country_raw(scenario, country)[0] | 0x80
            elif kind == 0xFF:
                head[0] = 0xC0
            head[3] = le16(rec, 6) // 100 + 1
            persons += head + rec + b"\0" * 4
        factions = bytearray()
        for f, r in enumerate(self.rulers(scenario)):
            factions += bytes([0xFF if r == 0xFF else 0, r, 0xFF, 0, 0])
        return {PERSON_WRAM: bytes(persons), COUNTRY_WRAM: bytes(countries), FACTION_WRAM: bytes(factions)}

    # --- strategic map, terrain ---
    def map_vram(self, scenario: int) -> bytes:
        """VRAM 0x0000-0x7FFF of the map at the start of the scenario (bank $19 + city markers)."""
        vram = bytearray(self.raw(MAP_BANK, 0x8000))
        start = self.scenario_wram(scenario)[COUNTRY_WRAM]
        for c in range(COUNTRY_COUNT):
            rec = start[COUNTRY_WRAM_SIZE * c + 1:COUNTRY_WRAM_SIZE * c + 17]
            x, y = self.position(c)
            col, row = 2 * (x & 0x3F) - 1, 2 * (y & 0x3F) - 1
            frame = 0 if rec[15] < 0x21 else 12 if rec[15] < 0x42 else 24
            for (dc, dr), t in zip(MAP_FRAME_OFFSETS, self.raw(MAP_MARKER_FRAMES + frame, 12)):
                vram[2 * ((row + dr) * MAP_TILES + col + dc)] = t
            a = rec[0] * 2 & 0x1E
            a = (a + 0x10 if a >= 0x10 else a) | 0xC0
            for dc, dr, t in ((0, 0, a), (1, 0, a + 1), (0, 1, a + 0x10), (1, 1, a + 0x11)):
                vram[2 * ((row + dr) * MAP_TILES + col + dc)] = t & 0xFF
        return bytes(vram)

    def map_cgram(self, month: int = 0, zoom: bool = False) -> bytes:
        """CGRAM (512 bytes) of the map in a month (0 = 1月), as $05:81B1 sets it."""
        cg = bytearray(self.raw(MAP_PALETTE, 0x200))
        cg[0x40:0x80] = self.raw(MAP_MONTH + 64 * month, 64)
        if zoom:
            cg[0x80:0xA0] = self.raw(MAP_MONTH_ZOOM + 32 * month, 32)
            for i in range(0x1E0, 0x200, 2):
                cg[i:i + 2] = cg[0x1E:0x20]
        else:
            cg[0x80:0xA0] = self.raw(MAP_MONTH_SMALL + 32 * month, 32)
            cg[0x1E0:0x200] = self.raw(MAP_SMALL_TOP, 32)
        return bytes(cg)

    def map_screen_palette(self, month: int = 0, zoom: bool = False) -> list[tuple[int, int, int]]:
        """256 colours as the map is shown: map_cgram with the window palette in rows 5, 14 and 15."""
        cg = bytearray(self.map_cgram(month, zoom))
        for r in WINDOW_ROWS:
            cg[32 * r:32 * r + 32] = self.raw(self.window_palette_at, 32)
        return palette(bytes(cg))

    def map_image_pixels(self, vram: bytes) -> list[int]:
        """1024 x 1024 colour numbers of a mode-7 VRAM image."""
        tiles = [vram[2 * i + 1] for i in range(0x4000)]   # char data: tile t = bytes 64 t .. 64 t + 63
        out = [0] * (1024 * 1024)
        for ty in range(MAP_TILES):
            for tx in range(MAP_TILES):
                t = vram[2 * (ty * MAP_TILES + tx)]
                for y in range(8):
                    o = (8 * ty + y) * 1024 + 8 * tx
                    out[o:o + 8] = tiles[64 * t + 8 * y:64 * t + 8 * y + 8]
        return out

    def terrain(self, x: int, y: int) -> int:
        return self.u8(TERRAIN + TERRAIN_SIZE * y + x)

    def terrain_name(self, kind: int) -> str:
        return self.text([self.u16(TERRAIN_NAMES + 4 * kind), self.u16(TERRAIN_NAMES + 4 * kind + 2)]).strip("　")

    def terrain_move(self, kind: int) -> int:
        return self.u8(self.terrain_move_at + kind)

    # --- faces ---
    def face_parts(self, f: int) -> bytes:
        return self.raw(self.face_parts_at + 11 * f, 11)

    def face_palette(self, f: int) -> list[tuple[int, int, int]]:
        """32 colours: OBJ palette 0 (shared) + palette 1 (this face)."""
        return palette(self.raw(FACE_SKIN, 32) + self.raw(self.face_palettes_at + 32 * f, 32))

    def face_buffer(self, f: int) -> bytes:
        """The sprite tile buffer $7E:8000 as $00:8B4D fills it (16 tiles per row, 8 rows, 4bpp)."""
        buf = bytearray(0x1000)
        for k, (base, step, width, tile) in enumerate(FACE_SLOTS):
            p = self.face_parts(f)[k]
            if p == 0xFF and k in FACE_OPTIONAL:
                continue
            src = self.raw(base + step * p, 2 * width)
            dst = 32 * tile
            if k == 10:  # $0145: rows of 0x40 bytes at 8C80 / 8E80 and 8CC0 / 8EC0 from one 0x80-byte part
                src = self.raw(base + step * p, 0x100)
                for j, d0 in enumerate((dst, dst + 0x200, dst + 0x40, dst + 0x240)):
                    buf[d0:d0 + 0x40] = src[0x40 * j:0x40 * j + 0x40]
                continue
            buf[dst:dst + width] = src[:width]
            buf[dst + 0x200:dst + 0x200 + width] = src[width:2 * width]
        return bytes(buf)

    def metasprite(self, i: int) -> list[tuple[int, int, int, int]]:
        p = 0x010000 | self.u16(META_TABLE + 2 * i)
        n = self.u8(p)
        return [struct.unpack_from("<bbBB", self.data, off(p) + 1 + 4 * k) for k in range(n)]

    def face_sprites(self, f: int) -> list[tuple[int, int, int, int]]:
        """OAM order (first = in front): extra sprites of the 4 special faces, then the face layout."""
        return (self.metasprite(FACE_EXTRA[f]) if f in FACE_EXTRA else []) + self.metasprite(FACE_META)

    def face_pixels(self, f: int) -> list[int]:
        """48 x 64 colour numbers 0-31 (palette 0/1 x 16; 0 and 16 = transparent -> -1)."""
        buf = self.face_buffer(f)
        tiles = {}

        def tile8(n):
            if n not in tiles:
                tiles[n] = decode_tile4(buf[32 * n:32 * n + 32])
            return tiles[n]

        px = [-1] * (FACE_W * FACE_H)
        for dx, dy, t, a in reversed(self.face_sprites(f)):  # back to front
            pal = (a >> 1 & 7) * 16
            hflip, vflip = a >> 6 & 1, a >> 7 & 1
            for ty in range(2):
                for tx in range(2):
                    src = tile8(t + 16 * ty + tx)
                    for y in range(8):
                        for x in range(8):
                            c = src[8 * y + x]
                            if not c:
                                continue
                            sx = (1 - tx) * 8 + (7 - x) if hflip else tx * 8 + x
                            sy = (1 - ty) * 8 + (7 - y) if vflip else ty * 8 + y
                            X, Y = dx + sx, dy + sy
                            if 0 <= X < FACE_W and 0 <= Y < FACE_H:
                                px[Y * FACE_W + X] = pal + c
        return px

    def face_rgb(self, f: int) -> list[tuple[int, int, int] | None]:
        pal = self.face_palette(f)
        return [None if c < 0 else pal[c] for c in self.face_pixels(f)]


def decode_fields(raw: bytes, fields) -> dict:
    return {name: raw[o] if n == 1 else le16(raw, o) for name, o, n in fields}


def decode_person(raw: bytes) -> dict:
    r = decode_fields(raw, PERSON_FIELDS)
    w = r.pop("武器")
    r["騎"], r["弓"], r["歩"] = w >> 2 & 3, w >> 4 & 3, w & 3   # 武器力 (detail screen, verify_persons.py)
    r["武器_raw"] = w
    r["レベル"] = r["経験値"] // 100 + 1
    return r
