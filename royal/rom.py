"""SFC スーパーロイヤルブラッド (KOEI, 1992; US: Gemfire) ROM decoding.

Offsets are file offsets of the headerless 1 MB LoROM image (CPU $bb:8000-$bb:FFFF = file bb * 0x8000 + addr - 0x8000).
The data tables are those of the FC version (~/works/famicom-re/royal): names in half-width katakana, the same 4
scenario blocks (only the header is laid out differently), units and 10x8 battle grids. Graphics are new.
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

DEFAULT_ROM = os.path.join(REPO, "roms", "Super Royal Blood (Japan).zip")
US_ROM = os.path.join(REPO, "roms", "Gemfire (USA).zip")

# ---------------------------------------------------------------- name tables (bank 1), same records as FC bank 19
CHAR_NAMES = 0xA900                 # 64 x 14: name (10), 0, age base, 0, unknown
CHAR_COUNT = 64
PROVINCE_NAMES = 0xAC80             # 30 x 21: name (11), 8 neighbours (FF = none), map marker cell x, y
PROVINCE_COUNT = 30
UNIT_NAMES = 0xAEF6                 # 23 x 18: name (10), 8 bytes
UNIT_COUNT = 23
HOUSE_NAMES = 0xB098                # 41 x 11 family names; 0-10 are the houses of the scenarios
HOUSE_NAME_COUNT = 41
US_OFFSET = -0x264                  # Gemfire (USA): the same four tables (ASCII names), 0x264 bytes earlier
ADVISOR_NAMES = 0x1C23C             # 4 x "ESC K ' ' name ESC H 0" (the advisor menu); faces 64-67
ADVISOR_COUNT = 4

# ---------------------------------------------------------------- scenarios
# Starting scenario s copies SCENARIO_SIZE bytes from SCENARIOS + SCENARIO_SIZE * s to WRAM $7E:C004 (verified
# with verify_scenarios.py). It is the FC block from its +4 on, the header re-laid out:
#   +2 years since scenario 1 (0, 5, 10, 15), +3 +4 = 0C 01, +6..+0x27 FF, +0x2A 05, +0x2B 01, +0x2D FF.
SCENARIOS = 0xB45A
SCENARIO_SIZE = 0x76C
SCENARIO_COUNT = 4
SCENARIO_WRAM = 0xC004
SCENARIO_NAMES = ["エランとレッドワルト", "フェリアス家のきき", "ティリアンの戦い", "ロイヤルブラッド"]
YEAR_OFFSET = 0x02
HOUSE_START, HOUSE_SIZE, HOUSE_SLOTS = 0x35, 4, 30      # (house id, lord, controller, flag bits), slot = house id
CHAR_START, CHAR_SIZE = 0xAD, 10                        # slot = character id = face
PROVINCE_START, PROVINCE_SIZE = 0x32D, 36
UNIT_SLOTS = 5                                          # province +16: 5 x (unit type, strength LE16, byte)
STATUS = {1: "当主", 2: "家臣", 4: "在野"}
# Lords of the 4 houses a player can choose, 4 bytes per scenario (in the p-code overlay; at WRAM $65CC while the
# house select screen runs). The screen takes its lords from here, not from the house records.
SELECTABLE_LORDS = 0x1C706

# ---------------------------------------------------------------- palettes (BG palettes 0-7 of CGRAM, 256 bytes)
STRATEGY_PALETTES = 0x111F8         # strategy screens (faces, map); OBJ palettes follow at 0x112F8
BATTLE_PALETTES = 0x113F8           # battle screen

# ---------------------------------------------------------------- faces
# 68 faces of 40x48 (5x6 4bpp tiles row-major, 960 bytes, uncompressed): 0-63 = character id, 64-67 = the 4
# advisors. 34 faces per 32 KB bank (the last 128 bytes of a bank are filler): face n at $13:8000 + 0x8000 * (n // 34)
# + 960 * (n % 34) in LoROM. The game DMAs the tiles straight from the ROM ($13:8F00 = face 4) and shows them with
# BG palette 1.
FACES = 0x98000
FACES_PER_BANK = 34
FACE_COUNT = 68
FACE_W, FACE_H = 5, 6
FACE_BYTES = 960
FACE_PALETTE = 1

# ---------------------------------------------------------------- strategy map
# BG2: 15x20 tilemap words at MAP_TILEMAP, drawn at tile (16, 3); 8x8 tiles from the LZ stream MAP_CHR loaded at
# tile MAP_TILE0 (BG chr base); palettes 5 and 6 of STRATEGY_PALETTES. The province numbers are in the picture;
# house markers are drawn on BG1 at the marker cells of the province table (BG1 tile (16 + x, 3 + y)? see docs).
MAP_TILEMAP = 0xE01E
MAP_W, MAP_H = 15, 20
MAP_ORIGIN = (16, 3)
MAP_CHR = 0x93E42
MAP_TILE0 = 0x12E

# ---------------------------------------------------------------- battle maps
# Grids: 30 x 80 bytes (10x8 cells row-major), high nibble = terrain (same bytes as FC); copied to WRAM $7E:FF00
# at the start of a battle (low nibble = unit). Cell (c, r) is metatile terrain on BG2 at tile (6 + 2c, 6 + 2r).
BATTLE_GRIDS = 0xD20A
BATTLE_W, BATTLE_H = 10, 8
BATTLE_ORIGIN = (6, 6)
BATTLE_WRAM = 0xFF00
METATILES = 0xF66A                  # 16 x 4 BG tilemap words (TL TR BL BR) per terrain
# BG chr loaded for a battle (tile, file offset, tile count); terrains 8-11 (water) use 8 animated tiles,
# 4 frames 0x20 bytes apart: frame 0 is listed
BATTLE_CHR = [(0x07, 0xDE900, 32), (0x37, 0xDED00, 16), (0x47, 0xDEF00, 10)] + [
    (t, o, 1) for t, o in zip((0x27, 0x28, 0x2B, 0x2D, 0x2F, 0x32, 0x33, 0x36),
                              (0xDF040, 0xDF0C0, 0xDF240, 0xDF340, 0xDF440, 0xDF5C0, 0xDF640, 0xDF7C0))]
WATER_FRAMES = 4
TERRAIN = {0: "平地", 1: "橋", 2: "守方本陣", 3: "攻方本陣", 4: "林", 5: "岩場", 6: "柵", 7: "柵(7)",
           8: "川(縦)", 9: "川(横)", 10: "川(角)", 11: "川(角2)", 12: "城壁(縦)", 13: "城壁(横)", 14: "城壁(角)",
           15: "城壁(角2)"}       # names from the pictures, not from the game


def lorom(addr: int) -> int:
    return (addr >> 16 & 0x7F) * 0x8000 + (addr & 0x7FFF)


def load_rom_bytes(path: str) -> bytes:
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
    else:
        with open(path, "rb") as f:
            data = f.read()
    return data[len(data) % 0x8000:]


def kana(raw: bytes) -> str:
    """Half-width katakana (cp932) up to the first 0, as full-width text."""
    return unicodedata.normalize("NFKC", raw.split(b"\0")[0].decode("cp932", errors="replace"))


def decode_tile(raw: bytes) -> list[int]:
    """One 4bpp SNES tile (32 bytes) -> 64 colour numbers, row-major."""
    out = []
    for y in range(8):
        p0, p1, p2, p3 = raw[2 * y], raw[2 * y + 1], raw[16 + 2 * y], raw[17 + 2 * y]
        for x in range(7, -1, -1):
            out.append((p0 >> x & 1) | (p1 >> x & 1) << 1 | (p2 >> x & 1) << 2 | (p3 >> x & 1) << 3)
    return out


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return tuple((c >> s & 31) << 3 | (c >> s & 31) >> 2 for s in (0, 5, 10))


def le16(raw: bytes, i: int) -> int:
    return raw[i] | raw[i + 1] << 8


def render_tilemap(words: list[int], w: int, chr_tiles: dict[int, bytes], palettes: list[list[int]]) -> list[int]:
    """BG tilemap words (row-major, w wide) -> RGB pixels; palettes = 8 BG palettes of 16 BGR555 colours.
    Colour 0 is drawn as colour 0 of palette 0 (the backdrop)."""
    h = len(words) // w
    out = [0] * (w * 8 * h * 8)
    for i, e in enumerate(words):
        px = decode_tile(chr_tiles[e & 0x3FF])
        pal = palettes[e >> 10 & 7]
        for k, v in enumerate(px):
            x, y = k % 8, k // 8
            if e & 0x4000:
                x = 7 - x
            if e & 0x8000:
                y = 7 - y
            out[(i // w * 8 + y) * w * 8 + i % w * 8 + x] = pal[v] if v else palettes[0][0]
    return [bgr555_rgb(c) for c in out]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        self.data = load_rom_bytes(path)
        self.lz_tables = koei_lz.find_tables(self.data)

    def u16(self, o: int) -> int:
        return le16(self.data, o)

    def palettes(self, o: int) -> list[list[int]]:
        return [[self.u16(o + 32 * p + 2 * i) for i in range(16)] for p in range(8)]

    # ------------------------------------------------------------ names

    def char_name(self, i: int) -> dict:
        r = self.data[CHAR_NAMES + 14 * i:CHAR_NAMES + 14 * i + 14]
        return {"name": kana(r[:10]), "age_base": r[11], "name_unknown": r[13]}

    def province_info(self, p: int) -> dict:
        r = self.data[PROVINCE_NAMES + 21 * p:PROVINCE_NAMES + 21 * p + 21]
        return {"name": kana(r[:11]), "neighbours": [x for x in r[11:19] if x != 0xFF], "marker": (r[19], r[20])}

    def house_name(self, h: int) -> str:
        return kana(self.data[HOUSE_NAMES + 11 * h:HOUSE_NAMES + 11 * h + 11])

    def advisor_names(self) -> list[str]:
        out, o = [], ADVISOR_NAMES
        for _ in range(ADVISOR_COUNT):
            end = self.data.index(b"\x1bH", o)
            out.append(kana(self.data[o + 2:end]).strip())
            o = end + 3
        return out

    def units(self) -> list[dict]:
        out = []
        for u in range(UNIT_COUNT):
            r = self.data[UNIT_NAMES + 18 * u:UNIT_NAMES + 18 * u + 18]
            out.append({"id": u, "name": kana(r[:10]), "a": r[11], "b": r[12], "hp": r[13], "c": r[15], "d": r[16],
                        "kind": r[17], "raw": r[10:].hex(" ")})
        return out

    # ------------------------------------------------------------ scenarios

    def scenario(self, s: int) -> bytes:
        o = SCENARIOS + SCENARIO_SIZE * s
        return self.data[o:o + SCENARIO_SIZE]

    def year_offset(self, s: int) -> int:
        return self.scenario(s)[YEAR_OFFSET]

    def selectable_lords(self, s: int) -> list[int]:
        return list(self.data[SELECTABLE_LORDS + 4 * s:SELECTABLE_LORDS + 4 * s + 4])

    def houses(self, s: int) -> list[dict]:
        b, out = self.scenario(s), []
        for k in range(HOUSE_SLOTS):
            h, lord, ctrl, bits = b[HOUSE_START + 4 * k:HOUSE_START + 4 * k + 4]
            if h != 0xFF:
                out.append({"id": h, "name": self.house_name(h), "lord": lord, "controller": ctrl, "bits": bits})
        return out

    def characters(self, s: int) -> list[dict]:
        """Characters present in scenario s (+5 = FF: absent)."""
        b, out = self.scenario(s), []
        off = self.year_offset(s)
        for i in range(CHAR_COUNT):
            r = b[CHAR_START + CHAR_SIZE * i:CHAR_START + CHAR_SIZE * (i + 1)]
            if r[5] == 0xFF:
                continue
            n = self.char_name(i)
            out.append({"id": i, **n, "age": n["age_base"] + off + 1, "int": r[2], "war": r[3], "charm": r[4],
                        "province": r[5], "house": r[6], "status": r[7],
                        "blood": None if r[8] == 0xFF else r[8], "lord_value": r[9]})
        return out

    def provinces(self, s: int) -> list[dict]:
        b, out = self.scenario(s), []
        for p in range(PROVINCE_COUNT):
            r = b[PROVINCE_START + PROVINCE_SIZE * p:PROVINCE_START + PROVINCE_SIZE * (p + 1)]
            units = []
            for k in range(UNIT_SLOTS):
                t, lo, hi, lv = r[16 + 4 * k:20 + 4 * k]
                if t != 0xFF:
                    units.append({"type": t, "hp": lo | hi << 8, "level": lv})
            out.append({"id": p, **self.province_info(p), "gold": le16(r, 2), "food": le16(r, 4), "men": le16(r, 6),
                        "land": r[8], "crops": r[9], "loyalty": r[10], "flags": r[11:14].hex(" "),
                        "owner": None if r[14] == 0xFF else r[14], "units": units})
        return out

    # ------------------------------------------------------------ faces

    def face_tiles(self, n: int) -> bytes:
        o = FACES + 0x8000 * (n // FACES_PER_BANK) + FACE_BYTES * (n % FACES_PER_BANK)
        return self.data[o:o + FACE_BYTES]

    def face_palette(self) -> list[int]:
        return self.palettes(STRATEGY_PALETTES)[FACE_PALETTE]

    def face_pixels(self, n: int) -> list[int]:
        """40x48 colour numbers (0-15) of face n, row-major."""
        tiles = self.face_tiles(n)
        out = [0] * (FACE_W * FACE_H * 64)
        for t in range(FACE_W * FACE_H):
            for i, v in enumerate(decode_tile(tiles[32 * t:32 * t + 32])):
                out[(t // FACE_W * 8 + i // 8) * FACE_W * 8 + t % FACE_W * 8 + i % 8] = v
        return out

    def face_rgb(self, n: int) -> list[tuple[int, int, int]]:
        pal = [bgr555_rgb(c) for c in self.face_palette()]
        return [pal[v] for v in self.face_pixels(n)]

    # ------------------------------------------------------------ strategy map

    def map_words(self) -> list[int]:
        return [self.u16(MAP_TILEMAP + 2 * i) for i in range(MAP_W * MAP_H)]

    def map_chr(self) -> bytes:
        return koei_lz.decompress(self.data, MAP_CHR, self.lz_tables)[0]

    def map_rgb(self) -> list[tuple[int, int, int]]:
        """120 x 160 pixels of the strategy map (without the house markers)."""
        chr_ = self.map_chr()
        tiles = {MAP_TILE0 + k: chr_[32 * k:32 * k + 32] for k in range(len(chr_) // 32)}
        return render_tilemap(self.map_words(), MAP_W, tiles, self.palettes(STRATEGY_PALETTES))

    # ------------------------------------------------------------ battle maps

    def battle_grid(self, p: int) -> bytes:
        o = BATTLE_GRIDS + BATTLE_W * BATTLE_H * p
        return self.data[o:o + BATTLE_W * BATTLE_H]

    def metatile(self, terrain: int) -> list[int]:
        return [self.u16(METATILES + 8 * terrain + 2 * k) for k in range(4)]

    def battle_words(self, p: int) -> list[int]:
        """20 x 16 BG2 tilemap words of the battlefield of province p (no units)."""
        w = BATTLE_W * 2
        out = [0] * (w * BATTLE_H * 2)
        for i, v in enumerate(self.battle_grid(p)):
            r, c = divmod(i, BATTLE_W)
            for k, e in enumerate(self.metatile(v >> 4)):
                out[(2 * r + k // 2) * w + 2 * c + k % 2] = e
        return out

    def battle_chr(self, frame: int = 0) -> dict[int, bytes]:
        """BG tiles of a battle by tile number (water tiles at animation frame `frame`)."""
        out = {}
        for t0, o, n in BATTLE_CHR:
            if n == 1:
                o += 0x20 * frame
            for k in range(n):
                out[t0 + k] = self.data[o + 32 * k:o + 32 * k + 32]
        return out

    def battle_rgb(self, p: int) -> list[tuple[int, int, int]]:
        """160 x 128 pixels of the battlefield of province p."""
        return render_tilemap(self.battle_words(p), BATTLE_W * 2, self.battle_chr(), self.palettes(BATTLE_PALETTES))


class UsNames:
    """English names from Gemfire (USA), the same tables 0x264 bytes earlier."""

    def __init__(self, path: str = US_ROM):
        self.data = load_rom_bytes(path) if os.path.exists(path) else b""

    def _name(self, o: int, n: int) -> str:
        return self.data[o:o + n].split(b"\0")[0].decode("ascii", errors="replace") if self.data else ""

    def char(self, i: int) -> str:
        return self._name(CHAR_NAMES + US_OFFSET + 14 * i, 10)

    def province(self, p: int) -> str:
        return self._name(PROVINCE_NAMES + US_OFFSET + 21 * p, 11)

    def unit(self, u: int) -> str:
        return self._name(UNIT_NAMES + US_OFFSET + 18 * u, 10)

    def house(self, h: int) -> str:
        return self._name(HOUSE_NAMES + US_OFFSET + 11 * h, 11)
