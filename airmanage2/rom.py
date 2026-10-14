"""SFC エアーマネージメントII 航空王をめざせ (KOEI) ROM decoding.

Headerless 1 MB LoROM image. Unlike the first game (KOEI p-code), the program is native 65816 code compiled from
C (banks $80-$8C, file 0x00000-0x67FFF). Graphics and other resources live in 196 named files (file table at
0x6000), many of them KOEI LZ streams (tools/koei_lz.py). Game tables are in bank $05 (pointer tables of 3-byte
pointers to Shift-JIS / half-width katakana strings and fixed-size records). See airmanage2/docs/ROM_FORMAT.md.
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Air Management II - Koukuu Ou o Mezase (Japan).zip")

FILE_TABLE = 0x6000             # 16-byte entries: name[8], bank LE16, addr LE16, size LE32; name[0] = 0 ends


def lorom(bank: int, addr: int) -> int:
    return (bank & 0x7F) * 0x8000 + (addr & 0x7FFF)


# ---------------------------------------------------------------- bank $05 tables (CPU address $05:xxxx)
CITY_COUNT = 89
CITY_NAME = 0xDEF1              # 89 pointers: half-width city name
CITY_WORLD_XY = 0xE233          # 89 x (x, y) bytes: city on the world map (pixels of the 256-wide map)
CITY_AREA_XY = 0xE2E5           # 89 x (x, y) bytes: city on its area map; the cursor hits it in [x, x+8] x [y, y+8]
AIRLINE_COUNT = 32
AIRLINE = 0xE397                # 32 pointers: default airline name of home city i (cities 0-31 can be home cities)
COUNTRY_COUNT = 57
COUNTRY = 0xE5CB                # 57 pointers: country name (0 = "ec", unused by the cities)
COUNTRY_E7DA = 0xE7DA           # 57 bytes copied to WRAM $2E21 at game start (unsolved)
TABLE_E815 = 0xE815             # 55 bytes (unsolved)
AREA_COUNT = 7
AREA_NAME = 0xE84C              # 7 pointers: area name
AREA_CITIES = 0xE8A6            # 7 x 4 bytes: first home city, count, first other city, count
AREA_HQ_MASK = 0xE8C6           # 7 x LE32: bit i = city i is a home city of this area
AIRCRAFT_COUNT = 53
AIRCRAFT_NAME = 0xE8E6          # 53 pointers
AIRCRAFT = 0xEBFE               # 53 x 11 bytes, see aircraft()
MAKER_COUNT = 12
MAKER_NAME = 0xEE45             # 12 pointers
MAKER_EEBC = 0xEEBC             # 12 bytes, used by the price rule (unsolved)
MAKER_FACE = 0xEEC7             # 12 x 4 bytes: face descriptor (kind LE16 = 2, image, palette)
MONTH = 0xEF05                  # 12 pointers
CITY_STATE_A = 0xF0FD           # 89 x 4 bytes: city record at the start of scenario 1 (country, 3 values)
CITY_STATE_B = 0xF261           # 89 x 4 bytes: the same at the start of scenario 4
CITY_SLOT_A = 0xF405            # 89 x 2 bytes: second city record, scenario 1
CITY_SLOT_B = 0xF4B7            # 89 x 2 bytes: second city record, scenario 4
INIT_COPIES = [(0xE7DA, 0x2E21, 57), (0xEF59, 0x2955, 192), (0xF019, 0x2AD5, 228), (0xF3C5, 0x3DF7, 64)]
DIFFICULTY = 0xF571             # 5 pointers
BUSINESS = 0xDAD3               # 15 pointers: related businesses (half-width)
BUSINESS_TYPE = 0xF83C          # 5 pointers: business categories
SCENARIO_NAME = (0x02, 0xF568)  # 8 pointers: 4 names, then 4 "(1955-1975)" year ranges
SCENARIO_COUNT = 4
SCENARIO_START_YEAR = [1955, 1970, 1985, 2000]   # the menu's year ranges; the game starts in APR
EVENTS = (0x0A, 0xFDC2)         # world events, 8 bytes each: year LE16, quarter LE16, message, target, type, value

# WRAM of the game state ($7E:xxxx), filled at game start ($82:B42C)
WRAM_SCENARIO = 0x24E9
WRAM_CITY = 0x2CBD              # 89 x 4 bytes
WRAM_CITY2 = 0x3E37             # 89 x 2 bytes

# ---------------------------------------------------------------- faces
# 40 x 48 = 5 x 6 4bpp tiles row-major, 960 bytes, copied to VRAM as is. Palettes: file FACEPAL, 30 x 16 colours
# (colour 0 transparent). A face is drawn ($04:8000) from a 4-byte descriptor: kind LE16, image, palette.
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
FACE_KINDS = ["SECRET", "STAFF", "MAKER", "MAYOR"]      # descriptor kind 0-3 = file
FACE_PALETTES = 30
# $82:AF85 / $82:B0A0: secretary and staff palette = base by the home city's area + random 0..3
# (area 0/4/5 -> 26, 1 -> 8, 2/6 -> 12, 3 -> 16); $8C:8634: mayor palette by the city's area (0/4/5 -> 0, 1 -> 1,
# 2/6 -> 2, 3 -> 3), image = country % 5.
AREA_PAL_BASE = {0: 26, 4: 26, 5: 26, 1: 8, 2: 12, 6: 12, 3: 16}
AREA_MAYOR_PAL = {0: 0, 4: 0, 5: 0, 1: 1, 2: 2, 6: 2, 3: 3}

# ---------------------------------------------------------------- font ($00:B8DE glyph lookup)
SYMBOL_TABLE = 0x3EE8           # bank 0 $BEE8: 21 SJIS codes (LE16)
KANJI_TABLE = 0x3F12            # bank 0 $BF12: 461 SJIS codes (LE16)
SYMBOL_COUNT, KANJI_COUNT = 21, 461
FONT_WIDE_BASE = 0x18D0         # FONT file: hiragana 83 x 32 bytes, then kanji 461 x 32 (16x16 1bpp)
FONT_KANJI_BASE = 0x18D0 + 0xA60
FONT_NARROW_TILE0 = 0xF3        # FONT[0:0x18D0] = 2bpp tiles 0xF3.. (VRAM $CF30); 8x16 glyph = tiles t, t+1
NARROW_BASE = {"symbol": 0x160, "digit": 0x18A, "alpha": 0x19E, "katakana": 0x1D2}

# ---------------------------------------------------------------- maps
# AREA1 holds 7 LZ streams, one per area (palette 32 bytes + 736 4bpp tiles); file offset of each in AREA1
AREA_STREAM = [0x0000, 0x23D1, 0x466A, 0x7041, 0x8BCF, 0xA3ED, 0xC62B]
AREA_MAP_W, AREA_MAP_H = 32, 23                 # AR_MAP: 32 x 23 tilemap words
WORLD_LAND_ROW = 3                               # MAINMAP tiles 0..479 fill rows 3-17 of the world map (BG1)
WORLD_SEA_TILE0 = 0x160                          # MAPBACK tile numbers start at BG2 tile 0x160 (VRAM $6C00)
WORLD_SEA_ROWS = 22


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return tuple(((c >> s) & 31) * 255 // 31 for s in (0, 5, 10))


def half_to_full(s: str) -> str:
    """A half-width name as the game shows it in full width: katakana via NFKC, ASCII to full-width letters
    (ec -> ｅｃ), long vowel as －."""
    s = unicodedata.normalize("NFKC", s).replace("ー", "－")
    return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in s)


def tiles4(data: bytes, n: int) -> list[list[list[int]]]:
    """n 8x8 4bpp SNES tiles -> [tile][y][x]."""
    out = []
    for t in range(n):
        o = t * 32
        out.append([[((data[o + 2 * y] >> (7 - x)) & 1) | ((data[o + 2 * y + 1] >> (7 - x)) & 1) << 1
                     | ((data[o + 16 + 2 * y] >> (7 - x)) & 1) << 2 | ((data[o + 17 + 2 * y] >> (7 - x)) & 1) << 3
                     for x in range(8)] for y in range(8)])
    return out


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.path = path
        if path.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                data = z.read(next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc"))))
        else:
            with open(path, "rb") as f:
                data = f.read()
        self.data = data[len(data) % 0x8000:]
        self.lz_tables = koei_lz.find_tables(self.data)

    # ------------------------------------------------------------ basics
    def b5(self, addr: int) -> int:
        return lorom(0x05, addr)

    def ptr(self, o: int) -> int:
        d = self.data
        return lorom(d[o + 2], d[o] | d[o + 1] << 8)

    def cstr(self, o: int) -> str:
        d = self.data
        return d[o:d.index(b"\0", o)].decode("cp932")

    def strings(self, addr: int, n: int, bank: int = 0x05) -> list[str]:
        o = lorom(bank, addr)
        return [self.cstr(self.ptr(o + 3 * i)) for i in range(n)]

    def files(self) -> list[dict]:
        out, o, d = [], FILE_TABLE, self.data
        while d[o]:
            bank, addr = d[o + 8] | d[o + 9] << 8, d[o + 10] | d[o + 11] << 8
            out.append({"index": len(out), "name": d[o:o + 8].split(b"\0")[0].decode("ascii"), "bank": bank,
                        "addr": addr, "offset": lorom(bank, addr), "size": int.from_bytes(d[o + 12:o + 16], "little")})
            o += 16
        return out

    def file(self, name: str) -> dict:
        return next(f for f in self.files() if f["name"] == name)

    def raw(self, name: str) -> bytes:
        f = self.file(name)
        return self.data[f["offset"]:f["offset"] + f["size"]]

    def lz(self, name: str, skip: int = 0) -> bytes:
        return koei_lz.decompress(self.data, self.file(name)["offset"] + skip, self.lz_tables)[0]

    # ------------------------------------------------------------ cities, areas, countries
    def areas(self) -> list[dict]:
        names = self.strings(AREA_NAME, AREA_COUNT)
        o, m = self.b5(AREA_CITIES), self.b5(AREA_HQ_MASK)
        d = self.data
        return [{"index": i, "name": names[i], "hq_first": d[o + 4 * i], "hq_count": d[o + 4 * i + 1],
                 "other_first": d[o + 4 * i + 2], "other_count": d[o + 4 * i + 3],
                 "hq_mask": int.from_bytes(d[m + 4 * i:m + 4 * i + 4], "little")} for i in range(AREA_COUNT)]

    def city_area(self, city: int) -> int:
        """$03:81A5: the area whose home-city range (cities < 32) or other-city range holds the city."""
        for a in self.areas():
            first, count = (a["hq_first"], a["hq_count"]) if city < 32 else (a["other_first"], a["other_count"])
            if first <= city < first + count:
                return a["index"]
        raise ValueError(city)

    def countries(self) -> list[dict]:
        names = self.strings(COUNTRY, COUNTRY_COUNT)
        e = self.data[self.b5(COUNTRY_E7DA):self.b5(COUNTRY_E7DA) + COUNTRY_COUNT]
        return [{"index": i, "name": names[i], "e7da": e[i]} for i in range(COUNTRY_COUNT)]

    def cities(self) -> list[dict]:
        d = self.data
        names = self.strings(CITY_NAME, CITY_COUNT)
        airlines = self.strings(AIRLINE, AIRLINE_COUNT)
        countries = self.strings(COUNTRY, COUNTRY_COUNT)
        w, a = self.b5(CITY_WORLD_XY), self.b5(CITY_AREA_XY)
        out = []
        for i in range(CITY_COUNT):
            country = d[self.b5(CITY_STATE_A) + 4 * i]
            area = self.city_area(i)
            out.append({"index": i, "name": names[i], "name_full": half_to_full(names[i]), "area": area,
                        "country": country, "country_name": countries[country],
                        "home": i < 32, "airline": airlines[i] if i < 32 else "",
                        "world_x": d[w + 2 * i], "world_y": d[w + 2 * i + 1],
                        "area_x": d[a + 2 * i], "area_y": d[a + 2 * i + 1]})
        return out

    # ------------------------------------------------------------ scenarios
    def scenarios(self) -> list[dict]:
        s = self.strings(SCENARIO_NAME[1], 8, SCENARIO_NAME[0])
        return [{"index": i, "name": s[i], "years": s[4 + i]} for i in range(SCENARIO_COUNT)]

    def events(self) -> list[dict]:
        """World events ($0A:FDC2, 55 records up to the first year outside 1950-2030): type 0 = city `target`
        changes country to `value`; type 1 = byte `target` of the country table $2E21 becomes `value` (meaning
        unsolved). message 255 = shown with the event before it. Events dated before a scenario's start year are
        already applied when the game starts ($0A:EA13)."""
        d, o, out = self.data, lorom(*EVENTS), []
        while True:
            e = d[o + 8 * len(out):o + 8 * len(out) + 8]
            year = e[0] | e[1] << 8
            if not 1950 < year < 2030:
                return out
            out.append({"index": len(out), "year": year, "quarter": e[2] | e[3] << 8, "message": e[4],
                        "target": e[5], "type": e[6], "value": e[7]})

    def scenario_cities(self, scenario: int) -> tuple[bytes, bytes]:
        """WRAM $2CBD (89 x 4) and $3E37 (89 x 2) as $82:B42C fills them: scenario 0 / 3 copy table A / B,
        1 and 2 take byte 0 from B and interpolate bytes 1-3 and byte 0 of the second record ($82:B6AC):
        a + trunc((b - a) * scenario / 3), clamped to 0..255. Then the type-0 world events before the start
        year set the country byte."""
        d = self.data
        a4, b4 = self.b5(CITY_STATE_A), self.b5(CITY_STATE_B)
        a2, b2 = self.b5(CITY_SLOT_A), self.b5(CITY_SLOT_B)
        if scenario in (0, 3):
            t4, t2 = (a4, a2) if scenario == 0 else (b4, b2)
            return self._apply_events(scenario, d[t4:t4 + 4 * CITY_COUNT]), d[t2:t2 + 2 * CITY_COUNT]

        def mix(a: int, b: int) -> int:
            v = a + int((b - a) * scenario / 3)
            return max(0, min(255, v))

        rec, rec2 = bytearray(), bytearray()
        for i in range(CITY_COUNT):
            rec.append(d[b4 + 4 * i])
            rec.extend(mix(d[a4 + 4 * i + k], d[b4 + 4 * i + k]) for k in (1, 2, 3))
            rec2.extend((mix(d[a2 + 2 * i], d[b2 + 2 * i]), 0))
        return self._apply_events(scenario, bytes(rec)), bytes(rec2)

    def _apply_events(self, scenario: int, rec: bytes) -> bytes:
        rec = bytearray(rec)
        for e in self.events():
            if e["type"] == 0 and e["year"] < SCENARIO_START_YEAR[scenario]:
                rec[4 * e["target"]] = e["value"]
        return bytes(rec)

    def init_tables(self, scenario: int = 0) -> dict[int, bytes]:
        """WRAM tables memcpy'd from bank $05 at game start: {WRAM address: bytes}; the country table $2E21 with
        the type-1 events before the scenario's start year applied."""
        out = {dst: bytearray(self.data[self.b5(src):self.b5(src) + n]) for src, dst, n in INIT_COPIES}
        for e in self.events():
            if e["type"] == 1 and e["year"] < SCENARIO_START_YEAR[scenario]:
                out[0x2E21][e["target"]] = e["value"]
        return {a: bytes(b) for a, b in out.items()}

    # ------------------------------------------------------------ aircraft, makers
    def makers(self) -> list[dict]:
        d = self.data
        names = self.strings(MAKER_NAME, MAKER_COUNT)
        e, f = self.b5(MAKER_EEBC), self.b5(MAKER_FACE)
        return [{"index": i, "name": names[i], "eebc": d[e + i],
                 "face_kind": d[f + 4 * i] | d[f + 4 * i + 1] << 8, "face_image": d[f + 4 * i + 2],
                 "face_palette": d[f + 4 * i + 3]} for i in range(MAKER_COUNT)]

    def aircraft(self) -> list[dict]:
        """11-byte records: maker, seats / 10, range km LE16, base price (万$) LE16, first year - 1900,
        last year - 1900 (200 = still built), 100 - fuel economy, 100 - maintainability, flags (unsolved)."""
        d = self.data
        names = self.strings(AIRCRAFT_NAME, AIRCRAFT_COUNT)
        o = self.b5(AIRCRAFT)
        out = []
        for i in range(AIRCRAFT_COUNT):
            r = d[o + 11 * i:o + 11 * i + 11]
            out.append({"index": i, "name": names[i], "maker": r[0], "seats": r[1] * 10,
                        "range_km": r[2] | r[3] << 8, "price": r[4] | r[5] << 8, "first_year": 1900 + r[6],
                        "last_year": None if r[7] == 200 else 1900 + r[7], "fuel": 100 - r[8],
                        "maintenance": 100 - r[9], "flags": r[10], "raw": bytes(r)})
        return out

    # ------------------------------------------------------------ faces
    def face_count(self, kind: int) -> int:
        return self.file(FACE_KINDS[kind])["size"] // FACE_BYTES

    def face_bytes(self, kind: int, image: int) -> bytes:
        return self.raw(FACE_KINDS[kind])[image * FACE_BYTES:(image + 1) * FACE_BYTES]

    def face_pixels(self, kind: int, image: int) -> list[list[int]]:
        t = tiles4(self.face_bytes(kind, image), FACE_W * FACE_H)
        return [[t[(y // 8) * FACE_W + x // 8][y % 8][x % 8] for x in range(FACE_W * 8)] for y in range(FACE_H * 8)]

    def face_palette(self, p: int) -> list[int]:
        b = self.raw("FACEPAL")[32 * p:32 * p + 32]
        return [b[2 * i] | b[2 * i + 1] << 8 for i in range(16)]

    def face_rgb(self, kind: int, image: int, palette: int) -> list[list[tuple[int, int, int]]]:
        pal = [bgr555_rgb(c) for c in self.face_palette(palette)]
        return [[pal[v] for v in row] for row in self.face_pixels(kind, image)]

    def mayor_face(self, city: int, country: int | None = None) -> tuple[int, int, int]:
        """$8C:8634: (kind 3, country % 5, palette by the city's area); country = byte 0 of the city record."""
        if country is None:
            country = self.data[self.b5(CITY_STATE_A) + 4 * city]
        return 3, country % 5, AREA_MAYOR_PAL[self.city_area(city)]

    def faces(self) -> list[dict]:
        """Portrait list for the exports: every image once with a representative palette, and the 12 maker
        descriptors. SECRET / STAFF: the first palette of the European set (26); MAYOR: palette 0 (Europe)."""
        out = []
        for kind, name in ((0, "SECRET"), (1, "STAFF"), (3, "MAYOR")):
            for i in range(self.face_count(kind)):
                out.append({"file": name, "kind": kind, "image": i, "palette": 0 if kind == 3 else 26})
        for m in self.makers():
            out.append({"file": "MAKER", "kind": m["face_kind"], "image": m["face_image"],
                        "palette": m["face_palette"], "maker": m["index"], "maker_name": m["name"]})
        return out

    # ------------------------------------------------------------ font
    def symbol_codes(self) -> list[int]:
        d = self.data
        return [d[SYMBOL_TABLE + 2 * i] | d[SYMBOL_TABLE + 2 * i + 1] << 8 for i in range(SYMBOL_COUNT)]

    def kanji_codes(self) -> list[int]:
        d = self.data
        return [d[KANJI_TABLE + 2 * i] | d[KANJI_TABLE + 2 * i + 1] << 8 for i in range(KANJI_COUNT)]

    def glyph(self, code: int) -> tuple[int, int, int]:
        """$00:B8DE: (kind, index, FONT offset). kind 0 = 16x16 1bpp at FONT offset (hiragana, kanji);
        kind 2 = 8x16 glyph drawn from the preloaded tiles NARROW_BASE + 2 * index (offset = FONT offset of the
        top tile). Codes not in the tables give kind 2 index 1 of the symbols (■)."""
        if code < 0x824F:
            sy = self.symbol_codes()
            i = sy.index(code) if code in sy else 1
            return 2, i, self._narrow("symbol", i)
        if code < 0x825F:
            i = code - 0x824F
            return 2, i, self._narrow("digit" if code < 0x8259 else "alpha", i)
        if code < 0x829E:
            i = code - (0x8260 if code < 0x8280 else 0x8281)
            return 2, i, self._narrow("alpha", i)
        if code < 0x833F:
            i = code - 0x829F
            return 0, i, FONT_WIDE_BASE + 32 * i
        if code < 0x839E:
            i = code - 0x8340
            return 2, i, self._narrow("katakana", i)
        k = self.kanji_codes()
        if code in k:
            i = k.index(code)
            return 0, i, FONT_KANJI_BASE + 32 * i
        return 2, 1, self._narrow("symbol", 1)

    @staticmethod
    def _narrow(group: str, i: int) -> int:
        return (NARROW_BASE[group] + 2 * i - FONT_NARROW_TILE0) * 16

    def font_chars(self) -> list[tuple[str, int]]:
        """(group, code) of every glyph the font draws: 21 symbols, 10 digits, 26 + 26 letters, 83 hiragana,
        86 katakana, 461 kanji."""
        out = [("symbol", c) for c in self.symbol_codes()]
        out += [("digit", 0x824F + i) for i in range(10)]
        out += [("alpha", 0x8260 + i) for i in range(26)] + [("alpha", 0x8281 + i) for i in range(26)]
        out += [("hiragana", 0x829F + i) for i in range(83)]
        out += [("katakana", 0x8340 + i) for i in range(0x8397 - 0x8340) if 0x8340 + i != 0x837F]
        out += [("kanji", c) for c in self.kanji_codes()]
        return out

    def glyph_pixels(self, code: int) -> list[list[int]]:
        """1 = ink. 16x16 for kind 0, 8x16 for kind 2."""
        font = self.raw("FONT")
        kind, _, off = self.glyph(code)
        if kind == 0:
            return [[(font[off + 8 * (2 * (y // 8) + x // 8) + y % 8] >> (7 - x % 8)) & 1 for x in range(16)]
                    for y in range(16)]
        return [[1 if ((font[off + 16 * (y // 8) + 2 * (y % 8)] | font[off + 16 * (y // 8) + 2 * (y % 8) + 1])
                       >> (7 - x)) & 1 else 0 for x in range(8)] for y in range(16)]

    # ------------------------------------------------------------ maps
    def world_map(self) -> list[list[tuple[int, int, int]]]:
        """256 x 176: sea (BG2, MAPBACK: palette 32 bytes, 22 x 32 tilemap, CHR) under the land (BG1, MAINMAP
        LZ = 480 tiles in rows 3-17, palette M_COLOR, colour 0 transparent)."""
        mb = self.raw("MAPBACK")
        sea_pal = [bgr555_rgb(mb[2 * i] | mb[2 * i + 1] << 8) for i in range(16)]
        tm_end = 0x20 + 2 * 32 * WORLD_SEA_ROWS
        sea_tiles = tiles4(mb[tm_end:], (len(mb) - tm_end) // 32)
        mc = self.raw("M_COLOR")
        land_pal = [bgr555_rgb(mc[2 * i] | mc[2 * i + 1] << 8) for i in range(16)]
        land = tiles4(self.lz("MAINMAP"), 480)
        img = [[(0, 0, 0)] * 256 for _ in range(8 * WORLD_SEA_ROWS)]
        for i in range(32 * WORLD_SEA_ROWS):
            e = mb[0x20 + 2 * i] | mb[0x21 + 2 * i] << 8
            t = sea_tiles[(e & 0x3FF) - WORLD_SEA_TILE0]
            for y in range(8):
                for x in range(8):
                    v = t[7 - y if e & 0x8000 else y][7 - x if e & 0x4000 else x]
                    img[i // 32 * 8 + y][i % 32 * 8 + x] = sea_pal[v]
        for t in range(480):
            for y in range(8):
                for x in range(8):
                    v = land[t][y][x]
                    if v:
                        img[(WORLD_LAND_ROW + t // 32) * 8 + y][t % 32 * 8 + x] = land_pal[v]
        return img

    def area_stream(self, area: int) -> bytes:
        """Palette (32 bytes) + 736 4bpp tiles of the area map."""
        return self.lz("AREA1", AREA_STREAM[area])

    def area_tilemap(self) -> list[int]:
        a = self.raw("AR_MAP")
        return [a[2 * i] | a[2 * i + 1] << 8 for i in range(AREA_MAP_W * AREA_MAP_H)]

    def area_map(self, area: int) -> list[list[tuple[int, int, int]]]:
        """256 x 184 area map: AR_MAP tilemap (tiles 0..735 of the area stream, palette 1) over the area's tiles."""
        s = self.area_stream(area)
        pal = [bgr555_rgb(s[2 * i] | s[2 * i + 1] << 8) for i in range(16)]
        tiles = tiles4(s[32:], (len(s) - 32) // 32)
        img = [[(0, 0, 0)] * (8 * AREA_MAP_W) for _ in range(8 * AREA_MAP_H)]
        for i, e in enumerate(self.area_tilemap()):
            t = tiles[e & 0x3FF]
            for y in range(8):
                for x in range(8):
                    v = t[7 - y if e & 0x8000 else y][7 - x if e & 0x4000 else x]
                    img[i // AREA_MAP_W * 8 + y][i % AREA_MAP_W * 8 + x] = pal[v]
        return img
