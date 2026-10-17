"""SFC スーパー伊忍道 打倒信長 (KOEI, 1995) ROM decoding.

Offsets are file offsets of the headerless 1.25 MB LoROM image ($bb:aaaa = file bb * 0x8000 + (aaaa & 0x7FFF)).
The game runs a p-code interpreter (data fetches at PC $00:006F) and keeps its code and tables in named files
listed at FILE_TABLE; the tables below are given as ROM offsets and noted with the file they sit in. See
docs/ROM_FORMAT.md. The US version (Inindo - Way of the Ninja) has the same file system; it is used only to
attach English names (persons, enemies), never as a source of data.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DEFAULT_ROM = os.path.join(REPO, "roms", "Super Inindou - Datou Nobunaga (Japan).zip")
US_ROM = os.path.join(REPO, "roms", "Inindo - Way of the Ninja (USA).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

# File table: 16-byte records [name 8][bank LE16][addr LE16][size LE32], a name starting with 0 ends it.
FILE_TABLE = 0x7800

# Text: 2-byte big-endian codes, glyph = code - TEXT_BASE (data/charset.txt), strings end with 0.
# Glyphs 0-13 are half-width pieces (two 8x16 halves per glyph: half h at FONT + 16 h, h = 2..11 are '0'..'9').
# Codes with a low byte of 0 cannot be stored (0 ends the string): ESCAPE + k stands for code 0x8200 + 0x100 k.
TEXT_BASE = 0x8132
GLYPH_COUNT = 1518
FONT = 0x88000                           # 16x16 1bpp, 32 bytes per glyph: tiles TL TR BL BR, one byte per row
ESCAPE = 0x89F0
ESCAPE_COUNT = 6

# data file (0x14930): persons, provinces, spells, generals, enemy skills, adjacency
PERSONS, PERSON_SIZE, PERSON_COUNT = 0x14934, 16, 105       # name 12 + [b12][b13][job][b15]
PROVINCES, PROVINCE_SIZE, PROVINCE_COUNT = 0x1502C, 6, 30   # name 4 + [0][value]
SPELLS, SPELL_SIZE, SPELL_COUNT = 0x150E0, 10, 42           # name 6 + [0][気力][b8][b9]
GENERALS, GENERAL_SIZE, GENERAL_COUNT = 0x15284, 17, 103    # name 15 + [v15][v16]; 0-15 are the daimyo
DAIMYO_COUNT = 16
ENEMY_SKILLS, ENEMY_SKILL_SIZE, ENEMY_SKILL_COUNT = 0x1595C, 9, 14   # name 6 + [0][b7][b8]
ADJACENCY, ADJACENCY_SIZE = 0x15B6A, 7                      # 30 x 7 province numbers, FF pads

# Jobs: names at JOB_NAMES (root file, 17 strings), person +14 is the job code
JOB_NAMES = 0xB79A
JOB_CODES = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x10, 0x11, 0x12, 0x13, 0x20, 0x21, 0x22, 0x30, 0x31, 0x32]
JOB_GROUPS = {0: "忍者", 1: "僧", 2: "陰陽", 3: "武"}

# sdata (0xF61E, 0xFE0 bytes): the initial game state, copied whole to WRAM $7E:EFF0 when a new game starts.
SDATA, SDATA_SIZE, SDATA_WRAM = 0xF61E, 0xFE0, 0xEFF0
BAG = 0x38                               # 45 bytes: 3 x 15 item numbers of the party, FF = empty
HERO_NAME = 0xBC                         # 12 bytes, the name typed on the naming screen
STATES, STATE_SIZE, STATE_COUNT = 0xC8, 32, 63              # person state records (+0 = person number)
VASSAL_NEXT = 0x8A8                      # 103 bytes: next general of the same province (from its lord), FF ends
DAIMYO_TABLE = 0x90F                     # 1 byte + 16 x [daimyo][value 0-4]
PROVINCE_STATES, PROVINCE_STATE_SIZE = 0x930, 18   # [daimyo][lord][金][米][兵 LE16][+8][+9][+10..17]

# rjdata file (0xD792): enemies, 38 bytes (name 15 + 23); the US file has the same 23 bytes after a 16-byte name
ENEMIES, ENEMY_SIZE, ENEMY_COUNT, ENEMY_NAME = 0xD796, 38, 180, 15
US_ENEMY_SIZE, US_ENEMY_NAME = 39, 16

# movl file (0x1D930): items, 16 bytes: [kind][name 11][price LE16][flags LE16]; 138 and 139 are placeholders
ITEMS, ITEM_SIZE, ITEM_COUNT = 0x1F110, 16, 138

# mmovl9 file: 18 place names (town, castle town and mountain names the travel messages use)
PLACE_NAMES, PLACE_COUNT = 0x39BE8, 18

# Job icons: 24x32 (3x4 tiles, 4bpp, row-major) at JOB_ICONS + 0x180 n, drawn by the status screens with BG
# palette 0. 16 icons for 17 jobs (伊賀女 and 甲賀女 share icon 3). The palette depends on the icon; which of
# the two the game picks was read from CGRAM (verify_faces.py), the selecting p-code is not traced.
JOB_ICONS, ICON_BYTES, ICON_W, ICON_H, ICON_COUNT = 0xD1500, 0x180, 3, 4, 16
JOB_ICON = [0, 1, 2, 3, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]     # by JOB_CODES order
ICON_PALETTES = (0x15E3C, 0x15E5C)
ICON_PALETTE = [0, 0, 1, 1, 1, 1, 1, 0, 0, 1, 0, 1, 0, 0, 0, 1]          # by icon

# Location maps: table at MAPS (LE16 offsets from MAPS, the first is 2 x count): [W][H][x][y] + RLE stream of
# W x H cell codes. RLE: byte b >= 0x80 is one cell b & 0x7F; b < 0x80 is followed by a count n: n cells b.
# The game unpacks to WRAM $7F:B000 + 4 (W + 8) + 4 (a 4-cell border, stride W + 8) with $7E:72A3.
# A cell is 32x32: 2x2 BG2 16x16 tiles from a metatile table (4 bytes per code, TL TR BL BR) whose byte v is
# 16x16 tile v of the tileset loaded at BG2 tile 0x20, palette 2. The town tileset (metatiles in overlay jovl1,
# tiles DMA'd by its p-code) is read from the game for the start village; maps 0-37 (castle towns, towns,
# villages) draw coherently with it, maps 38-47 do not and their tileset is not traced.
MAPS, MAP_COUNT = 0x7A000, 48
TOWN_METATILES = 0x326B0              # jovl1 file, 108 codes
METATILE_COUNT = 108
TOWN_TILESET, TOWN_TILESET_SIZE = 0x99F00, 0x1C00     # DMA to VRAM byte 0x4400 (tile 0x20)
TOWN_PALETTE = 0x15FDC                # CGRAM palette 2
TOWN_MAPS = range(38)
START_VILLAGE = 34                       # the map a new game starts in (伊賀の里)

STATE_FIELDS = {"体力": (2, 2), "最大体力": (4, 2), "気力": (6, 2), "最大気力": (8, 2), "経験値": (10, 2),
                "レベル": (12, 1), "知力": (15, 1), "素早さ": (16, 1), "運": (17, 1), "力": (22, 1)}


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
        cs = "".join(line for line in f.read().split("\n") if not line.startswith("#"))
    assert len(cs) == GLYPH_COUNT, len(cs)
    return cs


def lorom(bank: int, addr: int) -> int:
    return bank * 0x8000 + (addr & 0x7FFF)


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


def text_codes(raw: bytes) -> list[int]:
    """Codes up to the terminating 0, escapes resolved; a byte below 0x80 is a 1-byte code (seen: 0x20 spaces)."""
    out, i = [], 0
    while i < len(raw) and raw[i]:
        if raw[i] < 0x80 or i + 1 >= len(raw):
            out.append(raw[i])
            i += 1
            continue
        c = raw[i] << 8 | raw[i + 1]
        if ESCAPE <= c < ESCAPE + ESCAPE_COUNT:
            c = 0x8200 + 0x100 * (c - ESCAPE)
        out.append(c)
        i += 2
    return out


def decode_tile(raw: bytes, bpp: int = 4) -> list[int]:
    out = []
    for y in range(8):
        planes = [raw[2 * y], raw[2 * y + 1]] + ([raw[16 + 2 * y], raw[17 + 2 * y]] if bpp == 4 else [])
        for x in range(7, -1, -1):
            out.append(sum((p >> x & 1) << k for k, p in enumerate(planes)))
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return tuple((c >> s & 31) << 3 | (c >> s & 31) >> 2 for s in (0, 5, 10))


def file_table(d: bytes) -> list[dict]:
    out = []
    for i in range(FILE_TABLE, FILE_TABLE + 0x800, 16):
        if d[i] == 0:
            break
        out.append({"name": d[i:i + 8].split(b"\0")[0].decode("ascii"), "bank": le16(d, i + 8),
                    "addr": le16(d, i + 10), "offset": lorom(le16(d, i + 8), le16(d, i + 10)),
                    "size": int.from_bytes(d[i + 12:i + 16], "little")})
    return out


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.charset = load_charset()

    # --- files and text
    def files(self) -> list[dict]:
        return file_table(self.data)

    def char(self, code: int) -> str:
        if code < 0x80:
            return chr(code)
        g = code - TEXT_BASE
        return self.charset[g] if 14 <= g < GLYPH_COUNT else f"{{{code:04X}}}"

    def text(self, off: int, size: int) -> str:
        return "".join(self.char(c) for c in text_codes(self.data[off:off + size]))

    def string_at(self, off: int) -> tuple[str, int]:
        """A 0-terminated string and the offset after its terminator."""
        end = off
        while self.data[end] != 0:
            end += 2 if self.data[end] >= 0x80 else 1
        return self.text(off, end - off), end + 1

    def glyph(self, g: int) -> list[list[int]]:
        """16x16 bits of glyph g."""
        raw = self.data[FONT + 32 * g:FONT + 32 * g + 32]
        rows = []
        for y in range(16):
            top = raw[(y // 8) * 16 + y % 8]
            right = raw[(y // 8) * 16 + 8 + y % 8]
            rows.append([(top >> (7 - x)) & 1 for x in range(8)] + [(right >> (7 - x)) & 1 for x in range(8)])
        return rows

    # --- persons and jobs
    def jobs(self) -> list[dict]:
        out, off = [], JOB_NAMES
        for n, code in enumerate(JOB_CODES):
            name, off = self.string_at(off)
            out.append({"code": code, "name": name, "group": "主人公" if code == 0 else JOB_GROUPS[code >> 4],
                        "icon": JOB_ICON[n]})
        return out

    def job_names(self) -> dict[int, str]:
        return {j["code"]: j["name"] for j in self.jobs()}

    def persons(self) -> list[dict]:
        out = []
        for n in range(PERSON_COUNT):
            o = PERSONS + PERSON_SIZE * n
            r = self.data[o:o + PERSON_SIZE]
            out.append({"id": n, "name": self.text(o, 12), "b12": r[12], "b13": r[13], "job": r[14], "b15": r[15]})
        return out

    def sdata(self) -> bytes:
        return self.data[SDATA:SDATA + SDATA_SIZE]

    def states(self) -> list[dict]:
        sd, out = self.sdata(), []
        for k in range(STATE_COUNT):
            r = sd[STATES + STATE_SIZE * k:STATES + STATE_SIZE * (k + 1)]
            rec = {"record": k, "person": r[0], "raw": r}
            for name, (at, size) in STATE_FIELDS.items():
                rec[name] = r[at] if size == 1 else le16(r, at)
            rec["spell_masks"] = r[18:22]
            rec["equipment"] = list(r[23:28])
            rec["female"] = bool(r[31] & 0x80)
            out.append(rec)
        return out

    def bag(self) -> list[int]:
        return list(self.sdata()[BAG:BAG + 45])

    # --- generals, daimyo, provinces
    def generals(self) -> list[dict]:
        out = []
        for n in range(GENERAL_COUNT):
            o = GENERALS + GENERAL_SIZE * n
            out.append({"id": n, "name": self.text(o, 15), "v15": self.data[o + 15], "v16": self.data[o + 16]})
        return out

    def garrisons(self) -> dict[int, list[int]]:
        """Province -> its generals in the initial state: the lord, then VASSAL_NEXT from the lord (FF ends)."""
        nxt = self.sdata()[VASSAL_NEXT:VASSAL_NEXT + GENERAL_COUNT]
        out = {}
        for p in self.provinces():
            chain = [p["lord"]]
            while nxt[chain[-1]] != 0xFF and len(chain) < GENERAL_COUNT:
                chain.append(nxt[chain[-1]])
            out[p["id"]] = chain
        return out

    def daimyo_values(self) -> dict[int, int]:
        sd = self.sdata()
        return {sd[DAIMYO_TABLE + 1 + 2 * k]: sd[DAIMYO_TABLE + 2 + 2 * k] for k in range(DAIMYO_COUNT)}

    def provinces(self) -> list[dict]:
        sd, out = self.sdata(), []
        for n in range(PROVINCE_COUNT):
            o = PROVINCES + PROVINCE_SIZE * n
            a = ADJACENCY + ADJACENCY_SIZE * n
            s = sd[PROVINCE_STATES + PROVINCE_STATE_SIZE * n:PROVINCE_STATES + PROVINCE_STATE_SIZE * (n + 1)]
            out.append({"id": n, "name": self.text(o, 4), "value": self.data[o + 5],
                        "adjacent": [x for x in self.data[a:a + ADJACENCY_SIZE] if x != 0xFF],
                        "daimyo": s[0], "lord": s[1], "金": le16(s, 2), "米": le16(s, 4), "兵": le16(s, 6),
                        "s8": s[8], "s9": s[9], "rest": s[10:18]})
        return out

    # --- spells, items, enemies, places
    def spells(self) -> list[dict]:
        out = []
        for n in range(SPELL_COUNT):
            o = SPELLS + SPELL_SIZE * n
            r = self.data[o:o + SPELL_SIZE]
            out.append({"id": n, "name": self.text(o, 6).replace("　", "").replace(" ", ""), "気力": r[7], "b8": r[8], "b9": r[9]})
        return out

    def items(self) -> list[dict]:
        out = []
        for n in range(ITEM_COUNT):
            o = ITEMS + ITEM_SIZE * n
            r = self.data[o:o + ITEM_SIZE]
            out.append({"id": n, "kind": r[0], "name": self.text(o + 1, 11), "price": le16(r, 12),
                        "flags": le16(r, 14)})
        return out

    def enemy_skills(self) -> list[dict]:
        out = []
        for n in range(ENEMY_SKILL_COUNT):
            o = ENEMY_SKILLS + ENEMY_SKILL_SIZE * n
            out.append({"id": n, "name": self.text(o, 6).replace("　", ""), "b7": self.data[o + 7],
                        "b8": self.data[o + 8]})
        return out

    def enemies(self, us_names: dict[bytes, str] | None = None) -> list[dict]:
        out = []
        for n in range(ENEMY_COUNT):
            o = ENEMIES + ENEMY_SIZE * n
            body = self.data[o + ENEMY_NAME:o + ENEMY_SIZE]
            out.append({"id": n, "name": self.text(o, ENEMY_NAME), "data": body,
                        "en": (us_names or {}).get(body, "")})
        return out

    def place_names(self) -> list[str]:
        out, off = [], PLACE_NAMES
        for _ in range(PLACE_COUNT):
            name, off = self.string_at(off)
            out.append(name)
        return out

    # --- job icons
    def icon_tiles(self, n: int) -> bytes:
        return self.data[JOB_ICONS + ICON_BYTES * n:JOB_ICONS + ICON_BYTES * (n + 1)]

    def icon_palette_offset(self, n: int) -> int:
        return ICON_PALETTES[ICON_PALETTE[n]]

    def palette(self, off: int) -> list[int]:
        return [le16(self.data, off + 2 * k) for k in range(16)]

    def icon_pixels(self, n: int) -> bytes:
        """24x32 colour numbers (0-15), row-major."""
        raw, out = self.icon_tiles(n), bytearray(ICON_W * 8 * ICON_H * 8)
        for t in range(ICON_W * ICON_H):
            px = decode_tile(raw[32 * t:32 * t + 32])
            tx, ty = t % ICON_W, t // ICON_W
            for i, c in enumerate(px):
                out[(ty * 8 + i // 8) * ICON_W * 8 + tx * 8 + i % 8] = c
        return bytes(out)

    def icon_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.palette(self.icon_palette_offset(n))]
        return [pal[c] for c in self.icon_pixels(n)]

    # --- location maps
    def map_header(self, m: int) -> dict:
        off = MAPS + le16(self.data, MAPS + 2 * m)
        w, h, x, y = self.data[off:off + 4]
        return {"id": m, "offset": off, "w": w, "h": h, "x": x, "y": y}

    def map_count(self) -> int:
        return le16(self.data, MAPS) // 2

    def map_cells(self, m: int) -> tuple[list[int], int]:
        """W x H cell codes (row-major) and the offset after the stream."""
        hd = self.map_header(m)
        out, i, n = [], hd["offset"] + 4, hd["w"] * hd["h"]
        while len(out) < n:
            b = self.data[i]
            if b & 0x80:
                out.append(b & 0x7F)
                i += 1
            else:
                out += [b] * self.data[i + 1]
                i += 2
        return out[:n], i

    def map_wram(self, m: int) -> tuple[int, bytes]:
        """(WRAM offset, bytes) the game writes for map m: rows of W cells at stride W + 8 from $7F:B000 + 4 (W + 8)
        + 4 (only the cells; the border is filled separately)."""
        hd = self.map_header(m)
        cells, _ = self.map_cells(m)
        w, stride = hd["w"], hd["w"] + 8
        buf = bytearray(stride * (hd["h"] - 1) + w)
        for k, c in enumerate(cells):
            buf[(k // w) * stride + k % w] = c
        return 0x1B000 + 4 * stride + 4, bytes(buf)

    def town_metatiles(self) -> list[bytes]:
        return [self.data[TOWN_METATILES + 4 * c:TOWN_METATILES + 4 * c + 4] for c in range(METATILE_COUNT)]

    def town_tile_word(self, v: int) -> int:
        """BG2 tilemap word of metatile byte v: 16x16 tile v of the tileset (8 per row), loaded at tile 0x20."""
        return 0x0800 | (0x20 + (v // 8) * 32 + (v % 8) * 2)

    def render_town_map(self, m: int) -> tuple[int, int, list[tuple[int, int, int]]]:
        hd = self.map_header(m)
        cells, _ = self.map_cells(m)
        tiles = self.data[TOWN_TILESET:TOWN_TILESET + TOWN_TILESET_SIZE]
        pal = [bgr555_rgb(c) for c in self.palette(TOWN_PALETTE)]
        meta = self.town_metatiles()
        cache = {}

        def big(v: int) -> list[int]:           # 16x16 colour numbers of tileset tile v
            if v not in cache:
                px = [0] * 256
                for q in range(4):
                    t = (v // 8) * 32 + (v % 8) * 2 + (q % 2) + 16 * (q // 2)
                    for i, c in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                        px[((q // 2) * 8 + i // 8) * 16 + (q % 2) * 8 + i % 8] = c
                cache[v] = px
            return cache[v]

        w, h = hd["w"] * 32, hd["h"] * 32
        out = [(0, 0, 0)] * (w * h)
        for k, code in enumerate(cells):
            cx, cy = (k % hd["w"]) * 32, (k // hd["w"]) * 32
            for q, v in enumerate(meta[code]):
                px = big(v)
                for i, c in enumerate(px):
                    out[(cy + (q // 2) * 16 + i // 16) * w + cx + (q % 2) * 16 + i % 16] = pal[c]
        return w, h, out


def us_person_names(path: str = US_ROM) -> list[str]:
    """English person names of the US ROM (same 16-byte records, ASCII names), by person number."""
    u = load_rom_bytes(path)
    data = next(f for f in file_table(u) if f["name"] == "data")
    o = data["offset"] + 4
    return [u[o + PERSON_SIZE * n:o + PERSON_SIZE * n + 12].split(b"\0")[0].decode("ascii")
            for n in range(PERSON_COUNT)]


def us_enemy_names(path: str = US_ROM) -> dict[bytes, str]:
    """US enemy name by the 23 data bytes (identical in both versions); data shared by several records is left out."""
    u = load_rom_bytes(path)
    rj = next(f for f in file_table(u) if f["name"] == "rjdata")
    count = (rj["size"] - 4) // US_ENEMY_SIZE
    seen: dict[bytes, list[str]] = {}
    for n in range(count):
        o = rj["offset"] + 4 + US_ENEMY_SIZE * n
        seen.setdefault(u[o + US_ENEMY_NAME:o + US_ENEMY_SIZE], []).append(
            u[o:o + US_ENEMY_NAME].split(b"\0")[0].decode("ascii"))
    return {k: v[0] for k, v in seen.items() if len(set(v)) == 1}

