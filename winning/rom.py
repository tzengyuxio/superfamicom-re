"""SFC ウイニングポスト (KOEI, 1993) ROM decoding.

Headerless 2 MB HiROM image (original and Rev 1). Native 65816 code; graphics are KOEI LZ streams (tools/koei_lz.py,
one table of 769 3-byte pointers). Text uses the game's own 2-byte codes 0x8140 + glyph (data/charset.txt) mixed
with half-width kana bytes. The initial game state (horses, people, races) is a set of tables in bank $CF that a
new game copies into WRAM ($CB:4850). See winning/docs/ROM_FORMAT.md.

Offsets below are file offsets of the original release; Rev 1 moves some of them (REV1).
"""
import os
import sys
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import koei_lz

DEFAULT_ROM = os.path.join(REPO, "roms", "Winning Post (Japan).zip")
CHARSET = os.path.join(HERE, "data", "charset.txt")

# ---------------------------------------------------------------- offsets (original release)
ORIGINAL = {
    "LZ_POINTERS": 0x1C961,     # 769 x 3-byte pointers
    "SURNAME": 0x1921D,         # 256 x 3-byte pointers ($C1:921D): person surname
    "GIVEN": 0x1881D,           # 256 x 3-byte pointers ($C1:881D): person given name
    "TEMPLATE": 0x19A45,        # 828 x 10: horse name template, kana[9] + flag ($C1:9A45)
    "FOREIGN_NAME": 0x1BA9D,    # 100 x 11: foreign horse name, kana[9] + u16 ($C1:BA9D)
    "FIXED_NAME": 0xFD92F,      # 605 x 9: full horse names ($CF:D92F)
    "OWNER": 0xFD0C2,           # 41 x 24 ($CF:D0C2)
    "TRAINER": 0xFD49A,         # 30 x 22 ($CF:D49A)
    "JOCKEY_A": 0xFD777,        # 20 x 22: jockeys 0-19 (foreign, then 10 Japanese) ($CF:D777)
    "JOCKEY_B": 0xFBF24,        # 50 x 22: jockeys 20-69 ($CF:BF24)
    "HORSE_A": 0xF6B91,         # 400 x 37: racehorses 0-399 ($CF:6B91)
    "HORSE_B": 0xFB7DB,         # 24 x 37: racehorses 400-423 ($CF:B7DB)
    "STALLION": 0xFA561,        # 70 x 19 ($CF:A561)
    "MARE": 0xFAA93,            # 170 x 20 ($CF:AA93)
    "CALENDAR": 0xF41C6,        # 384 (+1) x 4: race programme ($CF:41C6)
    "RACE_CLASS": 0xD7DE9,      # 385 x u16: class of each programme slot ($CD:7DE9)
    "RACE_NAME": 0x5DAA3,       # 232 x 3-byte pointers ($C5:DAA3)
    "RACE_NTH": 0xAD742,        # 86 x u16: edition (第N回) of graded race r in 1997 ($CA:D742)
    "MEETING": 0x1C0DF,         # 12 months x (east, west): kai << 4 | track ($C1:C0DF)
    "TRACK": 0x1C1CF,           # 6-byte records: flags, name (2 glyphs), 0 ($C1:C1CF)
    "CLASS_SHORT": 0xBE0C1,     # 10 x 3-byte pointers ($CB:E0C1)
    "CLASS_LONG": 0xBE111,      # 10 x 3-byte pointers ($CB:E111)
    "AGE": 0xBE1D0,             # 4 x 3-byte pointers ($CB:E1D0)
    "SEX": 0xBE1F4,             # 4 x 3-byte pointers ($CB:E1F4)
    "DISTANCE": 0xBE20A,        # 12 bytes x 100 m ($CB:E20A)
    "TABLE_E216": 0xBE216,      # 12 x u16 (unsolved)
    "RANK": 0xBDE45,            # 4 x 3-byte pointers: A, B, C, ユーザー
    "APTITUDE": 0xBDEDF,        # 5 x 3-byte pointers: スプリンター ... 万能
    "COAT": 0xBDF26,            # 8 x 3-byte pointers: coat colours
    "MARKING": 0xBDF79,         # 16 x 3-byte pointers: face markings
    "LEG_MARKING": 0xBE02B,     # 3 x 3-byte pointers: 長白 / 白 / 微白
    "LEG": 0xBE041,             # 4 x 3-byte pointers: 左前 ... 右後
    "FARM": 0xBE061,            # 8 x 3-byte pointers: 早来専売 ... 十勝専売
    "FACE_PALETTE": 0x1DF43,    # 6 x 32 bytes ($C1:DF43, DF63, DF83, DFA3, DFC3, DFE3)
    "COMPOSITE_SHEET": 0x1CF2E,  # 8 x 3-byte pointers to the LZ part sheets of the composed faces ($C1:CF2E)
    "PART_CELL": 0xAE566,       # 8 types x 4 bytes: first cell of each part copy ($CA:E566)
    "PART_LEN": 0xAE586,        # 8 types x 4 bytes: cells in each copy ($CA:E586)
}
REV1 = dict(ORIGINAL, LZ_POINTERS=0x1C9A5, SURNAME=0x19261, GIVEN=0x18861, TEMPLATE=0x19A89, FOREIGN_NAME=0x1BAE1,
            RACE_NAME=0x5DB04, RACE_NTH=0xAD79E, MEETING=0x1C123, TRACK=0x1C213, CLASS_SHORT=0xBE0EF,
            CLASS_LONG=0xBE13F, AGE=0xBE1FE, SEX=0xBE222, DISTANCE=0xBE238, TABLE_E216=0xBE244, RANK=0xBDE73,
            APTITUDE=0xBDF0D, COAT=0xBDF54, MARKING=0xBDFA7, LEG_MARKING=0xBE059, LEG=0xBE06F, FARM=0xBE08F,
            FACE_PALETTE=0x1DF87, COMPOSITE_SHEET=0x1CF72, PART_CELL=0xAE5C2, PART_LEN=0xAE5E2)

LZ_COUNT = 769
PERSON_COUNT = 256
TEMPLATE_COUNT, FOREIGN_COUNT, FIXED_COUNT = 828, 100, 605
OWNER_COUNT, TRAINER_COUNT, JOCKEY_COUNT = 41, 30, 70
HORSE_COUNT, STALLION_COUNT, MARE_COUNT = 424, 70, 170
RACE_COUNT, CALENDAR_COUNT = 232, 384
GRADED_COUNT = 86                          # races 0-85 are graded (GI-GIII); 192-231 never appear in the programme
TRACK_COUNT = 8
MARE_ID, STALLION_ID = 400, 570            # horse id space ($C5:6040): < 400 racehorse, 400-569 mare, >= 570 stallion

# Trainer record byte 5, bits 0-5 ($CB:77C2 info window): (bit = 0, bit = 1) for 性格 方針 連闘 騎手起用 調教 相手比較
TRAINER_TRAIT_LABELS = ["性格", "方針", "連闘", "騎手起用", "調教", "相手比較"]
TRAINER_TRAITS = [("短気", "冷静"), ("現実主義", "理想主義"), ("たまにする", "滅多にしない"),
                  ("専属騎手優先", "こだわらない"), ("慎重", "スパルタ"), ("慎重", "強気")]

# The game state a new game copies from ROM into WRAM ($CB:4850 -> memcpy $C1:3379): (file offset, WRAM, size).
# Offsets are the same in both releases. Not listed: $CF:3875 is also copied to $9C12 (0x7D0 bytes, 400 x 5:
# the 5-byte record 00 FE FF 01 00 repeated), whose byte 4 is set to 0x80 right after the copy.
INIT_COPIES = [
    (0xF6231, 0x3AE6, 0x960), (0xF6B91, 0x4590, 0x39D0), (0xFB7DB, 0x7F60, 0x378), (0xFAA93, 0x274D, 0xD48),
    (0xFA561, 0x3495, 0x532), (0xFBB53, 0x847A, 0xFA), (0xFBC4D, 0x2041, 0x6E), (0xFC3E2, 0x2001, 0x40),
    (0xFC370, 0x20AF, 0x72), (0xFD72E, 0x2121, 0x28), (0xFBF24, 0x2301, 0x44C), (0xFD777, 0x2149, 0x1B8),
    (0xFBCBB, 0x39C7, 0x11F), (0xFBDDA, 0x4446, 0x14A), (0xF4045, 0x82F9, 0x181), (0xFD756, 0x82D8, 0x21),
    (0xF3875, 0xA3E2, 0x96), (0xF3875, 0xA478, 0x96), (0xF3875, 0xA4FA, 0x96),
    (0xF3875, 0xA590, 0x96), (0xF385D, 0xA63A, 0x18), (0xFEE74, 0xDA4A, 0x3EB),
]
# WRAM of the game state ($7E:xxxx)
WRAM_JOCKEY_A, WRAM_JOCKEY_B = 0x2149, 0x2301
WRAM_HORSE, WRAM_MARE, WRAM_STALLION = 0x4590, 0x274D, 0x3495
WRAM_YEAR, WRAM_MONTH = 0xDA60, 0xDA63
WRAM_USER_NAME = 0xA75E                     # 9-byte names the player typed (horse name word kind 0x28)

# ---------------------------------------------------------------- faces
# 40 x 48 = 5 x 6 4bpp tiles row-major (960 bytes). Codes 0x00-0xCF are portraits (LZ entry 287 + code); codes
# >= 0xD0 (bit 15 set in the data) are composed ($CA:223A). Palette by code range ($CA:2DA7).
FACE_W, FACE_H, FACE_BYTES = 5, 6, 960
FACE_ENTRY0, PORTRAIT_COUNT = 287, 208
SECRETARY_FACE = 0xCF
PALETTE_COUNT = 6                           # 0 = $C1:DF43 ... 5 = $C1:DFE3


def portrait_palette(code: int) -> int:
    """$CA:2DA7: palette number (0-5) of portrait code 0x00-0xCF."""
    if 0x28 <= code <= 0x9D:
        return 2                            # $DF83
    if code < 0x28 or code > 0xC4:
        return 3 if code == SECRETARY_FACE else 4   # $DFA3 / $DFC3
    return 5 if 0xA8 <= code <= 0xB5 else 3  # $DFE3 / $DFA3


def composite_fields(code: int) -> dict:
    """$CA:223A: type (bits 14-12) and the 4 part numbers (bits 1-0, 3-2, 5-4, 9-8) of a composed face code."""
    return {"type": code >> 12 & 7, "parts": [code & 3, code >> 2 & 3, code >> 4 & 3, code >> 8 & 3]}


def bgr555_rgb(c: int) -> tuple[int, int, int]:
    return tuple(((c >> s) & 31) * 255 // 31 for s in (0, 5, 10))


def decode_tile(b: bytes) -> list[int]:
    """One 8x8 4bpp SNES tile -> 64 colour indices, row-major."""
    return [((b[2 * y] >> (7 - x)) & 1) | ((b[2 * y + 1] >> (7 - x)) & 1) << 1
            | ((b[16 + 2 * y] >> (7 - x)) & 1) << 2 | ((b[17 + 2 * y] >> (7 - x)) & 1) << 3
            for y in range(8) for x in range(8)]


def tiles_pixels(data: bytes) -> list[int]:
    """30 tiles (5 x 6) -> 40 x 48 colour indices, row-major."""
    w = FACE_W * 8
    px = [0] * (w * FACE_H * 8)
    for t in range(FACE_W * FACE_H):
        tile = decode_tile(data[32 * t:32 * t + 32])
        tx, ty = t % FACE_W * 8, t // FACE_W * 8
        for i, v in enumerate(tile):
            px[(ty + i // 8) * w + tx + i % 8] = v
    return px


# ---------------------------------------------------------------- text
FONT_LO, FONT_HI = 0x000000, 0x1F0000      # glyphs 0-1023 at $C0:0000, 1024- at $DF:4000 (32 bytes each)
GLYPH_COUNT = 2368


def glyph_code(code: int) -> int:
    """$C2:0E5D: codes above 0x8A7F are 0x91xx escapes (0x9140 + k -> 0x8200 + k * 0x100) or blank (0x8140)."""
    if code <= 0x8A7F:
        return code
    return (0x8200 + ((code - 0x9140) << 8)) & 0xFFFF if code >= 0x9140 else 0x8140


def glyph_offset(code: int) -> int:
    """File offset of the 32 font bytes (four 1bpp 8x8 tiles TL TR BL BR) of a text code."""
    g = glyph_code(code) - 0x8140
    return FONT_LO + g * 32 if g < 0x400 else FONT_HI + ((g * 32 - 0x4000) & 0xFFFF)


def load_charset() -> str:
    with open(CHARSET, encoding="utf-8") as f:
        return "".join(line.rstrip("\n") for line in f if not line.startswith("#"))


# horse names: 1 byte per character ($C5:5D4E and the name entry screen)
KANA = {0x20: " ", 0x2D: "ー"}
for _b in range(0xA6, 0xDE):
    KANA[_b + 8] = unicodedata.normalize("NFKC", bytes([_b]).decode("cp932"))
for _i, _c in enumerate("ガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポヴ"):
    KANA[0xE6 + _i] = _c


def kana(b: bytes) -> str:
    """Horse-name bytes (until 0 / end) -> katakana; 0x20 is a space."""
    out = []
    for c in b:
        if c == 0:
            break
        out.append(KANA.get(c, f"[{c:02X}]"))
    return "".join(out)


def _strip(b: bytes, n: int) -> bytes:
    out = bytearray()
    for c in b[:n]:
        if c in (0, 0x20):
            break
        out.append(c)
    return bytes(out)


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
        self.revision = self.data[0xFFDB]
        self.o = REV1 if self.revision == 1 else ORIGINAL
        self.lz_tables = koei_lz.find_tables(self.data)
        self.charset = load_charset()
        self._lz = {}

    # ------------------------------------------------------------ basics
    def u16(self, o: int) -> int:
        return self.data[o] | self.data[o + 1] << 8

    def ptr(self, o: int) -> int:
        """3-byte HiROM pointer at file offset o -> file offset."""
        return int.from_bytes(self.data[o:o + 3], "little") & 0x3FFFFF

    def lz_entry(self, i: int) -> bytes:
        if i not in self._lz:
            self._lz[i] = koei_lz.decompress(self.data, self.ptr(self.o["LZ_POINTERS"] + 3 * i), self.lz_tables)[0]
        return self._lz[i]

    def text(self, o: int, limit: int = 256) -> str:
        return self.text_bytes(self.data[o:o + limit])

    def text_bytes(self, d: bytes) -> str:
        """Game string: 0x81-0x9F lead = glyph code 0x8140 + g; 0x91 xx = code 0x8200 + (xx - 0x40) * 0x100;
        1B 4B / 1B 48 switch half-width kana to katakana / hiragana (hiragana by default); 1B 43 n = colour;
        0x0A = new line; 0 ends."""
        cs = self.charset
        out, i, kata = [], 0, False
        while i < len(d) and d[i]:
            c = d[i]
            nxt = d[i + 1] if i + 1 < len(d) else 0
            if c == 0x91:
                g = (nxt - 0x40) * 0x100 + 0xC0
                out.append(cs[g] if 0 <= g < len(cs) else f"[91{nxt:02X}]")
                i += 2
            elif 0x81 <= c < 0xA0:
                g = (c << 8 | nxt) - 0x8140
                out.append(cs[g] if 0 <= g < len(cs) else f"[{c:02X}{nxt:02X}]")
                i += 2
            elif c == 0x1B:
                if nxt in (0x4B, 0x48):
                    kata = nxt == 0x4B
                    i += 2
                else:
                    i += 3
            elif c == 0x0A:
                out.append("\n")
                i += 1
            else:
                ch = unicodedata.normalize("NFKC", bytes([c]).decode("cp932", "replace"))
                if not kata and "ァ" <= ch <= "ヶ":
                    ch = chr(ord(ch) - 0x60)
                out.append(ch)
                i += 1
        return unicodedata.normalize("NFC", "".join(out))   # half-width ﾀﾞ -> た + U+3099 -> だ

    def strings(self, key: str, n: int) -> list[str]:
        o = self.o[key]
        return [self.text(self.ptr(o + 3 * i)) for i in range(n)]

    # ------------------------------------------------------------ people
    def person(self, i: int) -> tuple[str, str]:
        """(surname, given name) of person i ($C1:921D / $C1:881D; padded with full-width spaces)."""
        return (self.text(self.ptr(self.o["SURNAME"] + 3 * i)).rstrip("　 "),
                self.text(self.ptr(self.o["GIVEN"] + 3 * i)).rstrip("　 "))

    def persons(self) -> list[dict]:
        return [{"index": i, "surname": s, "given": g} for i in range(PERSON_COUNT) for s, g in [self.person(i)]]

    def _fixed_name(self, o: int, n: int) -> str:
        return kana(self.data[o:o + n]).strip()

    def owners(self) -> list[dict]:
        out = []
        for i in range(OWNER_COUNT):
            o = self.o["OWNER"] + 24 * i
            r = self.data[o:o + 24]
            out.append({"index": i, "face": self.u16(o), "surname": self.text(o + 5, 7).rstrip("　 "),
                        "given": self.text(o + 12, 7).rstrip("　 "), "crown": kana(_strip(r[19:24], 5)),
                        "crown_after": r[2] & 3 == 2, "data": r[2:5].hex()})
        return out

    def trainers(self) -> list[dict]:
        out = []
        for i in range(TRAINER_COUNT):
            o = self.o["TRAINER"] + 22 * i
            r = self.data[o:o + 22]
            out.append({"index": i, "face": self.u16(o), "jockey": 20 + r[2], "traits": r[5],
                        "trait_names": [TRAINER_TRAITS[b][r[5] >> b & 1] for b in range(6)],
                        "surname": self.text(o + 8, 7).rstrip("　 "), "given": self.text(o + 15, 7).rstrip("　 "),
                        "data": r[3:8].hex()})
        return out

    def jockey_record(self, i: int) -> bytes:
        o = self.o["JOCKEY_A"] + 22 * i if i < 20 else self.o["JOCKEY_B"] + 22 * (i - 20)
        return self.data[o:o + 22]

    def jockeys(self) -> list[dict]:
        out = []
        for i in range(JOCKEY_COUNT):
            r = self.jockey_record(i)
            s, g = self.person(r[21])
            out.append({"index": i, "face": r[0] | r[1] << 8, "person": r[21], "surname": s, "given": g,
                        "u2": r[2] | r[3] << 8, "b4": r[4], "b5": r[5], "b6": r[6], "b15": r[15], "b16": r[16],
                        "b17": r[17], "u18": r[18] | r[19] << 8, "b20": r[20], "data": r.hex()})
        return out

    # ------------------------------------------------------------ horse names
    def template(self, n: int) -> bytes:
        o = self.o["TEMPLATE"] + 10 * n
        return self.data[o:o + 10]

    def templates(self) -> list[dict]:
        return [{"index": n, "name": kana(self.template(n)[:9]).strip(), "flag": self.template(n)[9]}
                for n in range(TEMPLATE_COUNT)]

    def foreign_names(self) -> list[dict]:
        o = self.o["FOREIGN_NAME"]
        return [{"index": n, "name": self._fixed_name(o + 11 * n, 9), "value": self.u16(o + 11 * n + 9)}
                for n in range(FOREIGN_COUNT)]

    def fixed_names(self) -> list[str]:
        o = self.o["FIXED_NAME"]
        return [self._fixed_name(o + 9 * n, 9) for n in range(FIXED_COUNT)]

    def horse_name(self, w: int, user: list[bytes] | None = None) -> str:
        """$C5:5D4E: horse name word -> name. k = w >> 10, n = w & 0x3FF.
        k < 40: owner k's crown (5) + template n (9), or template + crown when the owner's flag says so;
        n > 0x315 uses the template alone. k = 0x28: name typed by the player (WRAM $A75E + 9n);
        k = 0x29: fixed name n ($CF:D92F); k = 0x2A: foreign name n; k = 0x2C: template (n >> 5) + 0x2DE
        followed by template n & 31; other k: fixed name 0 (empty; k = 0x2B also prints a debug message).
        Names are cut at 9 characters."""
        k, n = w >> 10, w & 0x3FF
        if k < 40:
            t = self.template(n)
            if n > 0x315:
                return kana(t[:9]).strip()
            o = self.o["OWNER"] + 24 * k
            crown = _strip(self.data[o + 19:o + 24], 5)
            s = _strip(t, 9) + crown if self.data[o + 2] & 3 == 2 else crown + _strip(t, 9)
            return kana(s[:9])
        if k == 0x28:
            return kana(user[n]).strip() if user else f"<user {n}>"
        if k == 0x2A:
            return self._fixed_name(self.o["FOREIGN_NAME"] + 11 * n, 9)
        if k == 0x2C:
            return kana((_strip(self.template((n >> 5) + 0x2DE), 9) + _strip(self.template(n & 31), 9))[:9])
        if k == 0x29:
            return self._fixed_name(self.o["FIXED_NAME"] + 9 * n, 9)
        return self._fixed_name(self.o["FIXED_NAME"], 9)

    # ------------------------------------------------------------ horses
    def _horse_ref(self, hid: int) -> dict:
        if hid == 0xFFFF:
            return {"kind": "", "index": None}
        if hid < MARE_ID:
            return {"kind": "horse", "index": hid}
        if hid < STALLION_ID:
            return {"kind": "mare", "index": hid - MARE_ID}
        if hid < STALLION_ID + STALLION_COUNT:
            return {"kind": "stallion", "index": hid - STALLION_ID}
        return {"kind": "pedigree", "index": hid}          # beyond the id space: unsolved

    def _horses(self, key_list, size: int) -> list[dict]:
        out = []
        for key, count in key_list:
            for i in range(count):
                o = self.o[key] + size * i
                r = self.data[o:o + size]
                out.append({"index": len(out), "name_word": self.u16(o), "used": r[0:2] != b"\xdf\xa4",
                            "sire": self.u16(o + 2), "dam": self.u16(o + 4), "data": r[6:].hex()})
        for h in out:
            h["name"] = self.horse_name(h["name_word"]) if h["used"] and h["name_word"] != 0xFFFF else ""
        return out

    def horses(self) -> list[dict]:
        hs = self._horses([("HORSE_A", 400), ("HORSE_B", 24)], 37)
        for h in hs:
            h["used"] = h["used"] and h["name"] != ""
        return hs

    def stallions(self) -> list[dict]:
        hs = self._horses([("STALLION", STALLION_COUNT)], 19)
        for h in hs:
            h["used"] = h["name_word"] != 0xFFFF and h["name"] != ""
        return hs

    def mares(self) -> list[dict]:
        hs = self._horses([("MARE", MARE_COUNT)], 20)
        for h in hs:
            h["used"] = h["name_word"] != 0xFFFF and h["name"] != ""
        return hs

    def horse_label(self, hid: int) -> str:
        ref = self._horse_ref(hid)
        if ref["kind"] == "horse":
            return self.horses()[ref["index"]]["name"]
        if ref["kind"] == "mare":
            return self.mares()[ref["index"]]["name"]
        if ref["kind"] == "stallion":
            return self.stallions()[ref["index"]]["name"]
        return ""

    # ------------------------------------------------------------ races
    def race_names(self) -> list[str]:
        return self.strings("RACE_NAME", RACE_COUNT)

    def tracks(self) -> list[dict]:
        o = self.o["TRACK"]
        return [{"index": i, "flags": self.data[o + 6 * i], "name": self.text(o + 6 * i + 1, 4)}
                for i in range(TRACK_COUNT)]

    def meeting(self, month: int, west: int) -> tuple[int, int]:
        """(kai, track) of a month (1-12) and side (0 = east, 1 = west)."""
        v = self.data[self.o["MEETING"] + (month - 1) * 2 + west]
        return v >> 4, v & 15

    def calendar(self) -> list[dict]:
        """The race programme: slot i = month i // 32 + 1, week (i % 32) // 8 + 1, race (i % 8) // 2, side i % 2
        (0 = east, 1 = west). b0 = race number (0xFF = no named race); b1 = distance << 4 | sex << 2 | age."""
        names = self.race_names()
        tracks = [t["name"] for t in self.tracks()]
        cls_s, cls_l = self.strings("CLASS_SHORT", 10), self.strings("CLASS_LONG", 10)
        ages, sexes = self.strings("AGE", 4), self.strings("SEX", 4)
        dist = self.data[self.o["DISTANCE"]:self.o["DISTANCE"] + 12]
        nth = [self.u16(self.o["RACE_NTH"] + 2 * r) for r in range(GRADED_COUNT)]
        out = []
        for i in range(CALENDAR_COUNT):
            b = self.data[self.o["CALENDAR"] + 4 * i:self.o["CALENDAR"] + 4 * i + 4]
            cw = self.u16(self.o["RACE_CLASS"] + 2 * i)
            month, west = i // 32 + 1, i % 2
            kai, track = self.meeting(month, west)
            race = None if b[0] == 0xFF else b[0]
            out.append({"slot": i, "month": month, "week": i % 32 // 8 + 1, "race_no": i % 8 // 2, "west": west,
                        "kai": kai, "track": track, "track_name": tracks[track],
                        "race": race, "race_name": names[race] if race is not None else "",
                        "nth_1997": nth[race] if race is not None and race < GRADED_COUNT else None,
                        "class": cw & 15, "class_short": cls_s[cw & 15], "class_long": cls_l[cw & 15],
                        "class_hi": cw >> 4, "distance": dist[b[1] >> 4] * 100, "age": ages[b[1] & 3],
                        "sex": sexes[b[1] >> 2 & 3], "b2": b[2], "b3": b[3]})
        return out

    # ------------------------------------------------------------ small name tables
    def name_tables(self) -> dict[str, list[str]]:
        return {"rank": self.strings("RANK", 4), "aptitude": self.strings("APTITUDE", 5),
                "coat": self.strings("COAT", 8), "marking": self.strings("MARKING", 16),
                "leg_marking": self.strings("LEG_MARKING", 3), "leg": self.strings("LEG", 4),
                "farm": self.strings("FARM", 8), "class_short": self.strings("CLASS_SHORT", 10),
                "class_long": self.strings("CLASS_LONG", 10), "age": self.strings("AGE", 4),
                "sex": self.strings("SEX", 4)}

    # ------------------------------------------------------------ faces
    def palette(self, n: int) -> list[int]:
        """BGR555 colours of face palette n (0-5)."""
        o = self.o["FACE_PALETTE"] + 32 * n
        return [self.u16(o + 2 * i) for i in range(16)]

    def palette_offset(self, n: int) -> int:
        return self.o["FACE_PALETTE"] + 32 * n

    def portrait_bytes(self, code: int) -> bytes:
        return self.lz_entry(FACE_ENTRY0 + code)

    def composite_sheet(self, t: int) -> bytes:
        """LZ part sheet of composed-face type t: 4 faces x 30 tiles."""
        p = self.ptr(self.o["COMPOSITE_SHEET"] + 3 * t)
        return koei_lz.decompress(self.data, p, self.lz_tables)[0]

    def part_copies(self, t: int) -> list[tuple[int, int, int]]:
        """$CA:223A: the copies that build a type-t face, [(part slot, first cell, cells)]: cells 0-14 from part 0,
        15-29 from part 1, then two runs from part 2 and two from part 3 (a run of 0 cells is skipped)."""
        cell = self.data[self.o["PART_CELL"] + 4 * t:self.o["PART_CELL"] + 4 * t + 4]
        n = self.data[self.o["PART_LEN"] + 4 * t:self.o["PART_LEN"] + 4 * t + 4]
        out = [(0, 0, 15), (1, 15, 15)]
        for j in range(4):
            if n[j]:
                out.append((2 + j // 2, cell[j], n[j]))
        return out

    def composite_bytes(self, code: int) -> bytes:
        """The 960 tile bytes the game builds at $7F:8F00 for a composed face code."""
        f = composite_fields(code)
        sheet = self.composite_sheet(f["type"])
        buf = bytearray(FACE_BYTES)
        for slot, first, n in self.part_copies(f["type"]):
            src = (f["parts"][slot] * 30 + first) * 32
            buf[first * 32:(first + n) * 32] = sheet[src:src + n * 32]
        return bytes(buf)

    def face_bytes(self, code: int) -> bytes:
        return self.portrait_bytes(code) if code < PORTRAIT_COUNT else self.composite_bytes(code)

    def face_palette_number(self, code: int) -> int:
        if code < PORTRAIT_COUNT:
            return portrait_palette(code)
        return 0 if composite_fields(code)["type"] < 4 else 1

    def face_rgb(self, code: int) -> list[list[tuple[int, int, int]]]:
        pal = [bgr555_rgb(c) for c in self.palette(self.face_palette_number(code))]
        px = tiles_pixels(self.face_bytes(code))
        w = FACE_W * 8
        return [[pal[v] for v in px[y * w:(y + 1) * w]] for y in range(FACE_H * 8)]
