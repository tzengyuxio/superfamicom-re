"""Dump the music as SPC files and render them to OGG and MP3, with the lengths read from the song data.

Usage: .venv/bin/python yokoyama/tools/music.py [--rom ROM] [--loops 2] [--fade 10]
       → yokoyama/output/music/BB-NN_<kind>_<use>.spc / .ogg (Opus 96k) / .mp3 (LAME VBR -q:a 2), music.csv
       (BB = sound set bank, NN = song number; kind bgm = loops, jingle = ends; use unknown when not known; see
       ~/.claude/re-common.md §10)

The 65816 sends sound commands through $2140: $00:9729 sends 83 (wait for $80 back), then $00:9742 sends 02 right
after the title (LDA #$02 ; STA $2140). Songs live in 3 sound sets that $10:F39C uploads whole (see SET_OPERANDS):
driver, song table and every song of the set. One Mesen run per set patches the set and has the game start song 01
(silent) in place of 02; SHOT frames later the SPC700 state is dumped (64 KB RAM, 128 DSP registers, CPU registers,
I/O registers $F0-$FF) in the SPC file format (v0.30). Every song of the set is that state with input port 0 set to
the song number: the driver's main loop ($0969) reads the port and starts the song from its first tick.

The driver (TOSE, a variant of Nintendo's N-SPC) keeps the song table at $191E (song n at $191C + 2n, read at
$0B35), a song is a block list (word >= $100 = block of 8 track pointers; 0000 = end; 00nn + address = jump, nn >= $80
forever, else nn more times), tracks use the N-SPC bytes (01-7F length, 80-DF note/tie/rest/percussion, E0-FE commands
with the parameter lengths at $114D; EF = subroutine) and a block ends with track 0. A tick passes when the tempo
($63, set by E7) added at every 2 ms timer step carries out of 8 bits: 500 x tempo / 256 ticks a second. 前奏秒 and
循環秒 come from that; the SPC's ID666 length and the OGG / MP3 are intro + --loops loops (once for a song that ends), then
--fade seconds of fade-out. Trying 00-7F in every set found songs only at 01-18 and 41-58; 41-58 start the same block
lists as 01-18 (bit 6 goes to $0637), so only 01-18 are made. Numbers sharing a block list are listed once, and a song
with less than 3 seconds of sound is dropped. music.csv adds the [EXT] columns of data/music_zophar.tsv (Zophar's
Domain SPC set matched to set and song number).
"""
import argparse
import array
import csv
import ctypes
import os
import subprocess
import sys
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(os.path.dirname(GAME), "tools"))
from paths import ORIGINAL
from replay import replay

ROM = os.path.join(ORIGINAL, "Yokoyama Mitsuteru Sangokushi (Japan).zip")
# $10:F39C uploads a whole sound set (driver + songs) through the IPL: argument 1 -> $1C:8000, 2 -> $1E:8000,
# else $1A:8000. A run patches the three bank operands (LDA #$1C / #$1E / #$1A) to one set, so the upload that
# follows the 83 loads it.
SET_OPERANDS = [0x873CA, 0x873D3, 0x873DC]
SONG_OPERAND = 0x1743   # file offset of the 02 in LDA #$02 at $00:9742 (Rev 0): patched to 01, a silent song
SETS = [0x1A, 0x1C, 0x1E]
BOOT = "w1200 start:10"  # to the title screen
SAVE_AT = 1950
STEPS = "w84 a:10"      # from the savestate: 83 at frame 2034, the song command at 2263
SHOT = 330              # frames after the savestate: song 01 is playing (the upload is over)
LIBGME = "/opt/homebrew/opt/game-music-emu/lib/libgme.dylib"
RATE = 32000
# Songs whose scene is known: "BB-NN" -> (use, basis) (docs/ROM_FORMAT.md §11). emu = logging $2140 in natural
# play; code = the handler sends the song (LDX #nn ; STX $2140) right before the command's picture ($00:C58F) and
# its result message (message table $1F:BD88). A command jingle is shared by several commands: the use names the
# first one, the basis lists all.
USES = {
    "1E-02": ("title", "用途 ✅ emu（$2140 log）"),
    "1A-02": ("scenario-menu", "用途 ✅ emu（$2140 log）"),
    "1C-0C": ("opening", "用途 ✅ emu（$2140 log）"),
    "1C-02": ("policy-phase", "用途 ✅ emu（$2140 log：政略フェイズ，場景表 $00:A696）"),
    "1C-03": ("military-phase", "用途 ✅ emu（$2140 log：軍略フェイズ）"),
    "1C-04": ("march-phase", "用途 ✅ emu（$2140 log：行軍フェイズ）"),
    "1C-05": ("disaster-prevention", "用途 ✅ code（防災 $00:AA16、同盟 $00:ACCA、訓練 $00:AE2B）"),
    "1C-06": ("develop", "用途 ✅ code（開発 農業 $00:A900、産業 $00:A936；$00:B535）"),
    "1C-07": ("tax", "用途 ✅ code（租税 徴収 $00:A9F3、徴兵 $00:ADB6、兵移動 $00:ADF8）"),
    "1C-08": ("reward", "用途 ✅ code（褒美 忠誠度 $00:A9A6）"),
    "1C-09": ("scheme", "用途 ✅ code（同盟破棄 $00:ACFB／$00:AEAB、引き抜き $00:AF2A／$00:AF57；$00:AEE5）"),
    "1C-0A": ("plot", "用途 ✅ code（計略 $00:B1E0／$00:B1FE、伏兵 $00:B243、奇襲 $00:B294）"),
    "1C-0B": ("transport", "用途 ✅ code（輸送 $00:ABF5；$00:B4FC）"),
    "1C-0D": ("appoint", "用途 ✅ code（太守任命 $00:AB02、軍師任命 $00:AB1E；$00:A426／$00:A473）"),
    "1C-0E": ("revolt", "用途 ✅ emu（$2140 log：自國住民反乱，$01:DFC1）；也給 $00:AB3A；Zophar 曲名 Bad Event for Player"),
    "1C-0F": ("sortie", "用途 ✅ code（出陣 $00:B4AD、城塞 $00:AE4D、武器強化 $00:AFF7；$00:B54B）"),
    "1C-10": ("govern", "用途 ✅ code（統治 $00:A987、戰術 火計 $00:D091）"),
    "1C-11": ("land", "用途 ✅ code（國土開発 人口 $00:A955、戰術 落石 $00:D0F8、罵声 $00:D1B9）"),
    "1C-12": ("search", "用途 ✅ code（人材探索 $00:AB4D、戰術 酒盛り $00:D124）"),
    "1C-13": ("move", "用途 ✅ code（武將移動 $00:AA7B）"),
    "1C-17": ("kongming-visit", "用途 ✅ code（$00:AB8E：劉備親自探索、找到孔明時，訊息 0x155／0x156）"),
    "1C-18": ("bad-event", "用途 🟡 code（$01:EA11 災害動畫，送 18）；Zophar 曲名 Bad Event"),
}

SPC_LUA = """
function EXTRA_SHOT()
  local s=emu.getState()
  local t={}
  local function b(v) t[#t+1]=string.format("%02x", v & 255) end
  b(s["spc.pc"]) b(s["spc.pc"] >> 8) b(s["spc.a"]) b(s["spc.x"]) b(s["spc.y"]) b(s["spc.ps"]) b(s["spc.sp"])
  local ctl=0
  for i=0,2 do if s["spc.timer"..i..".enabled"] then ctl=ctl | (1 << i) end end
  b(ctl) b(s["spc.dspReg"])
  for i=0,3 do b(s["spc.cpuRegs["..i.."]"]) end
  b(s["spc.ramReg[0]"]) b(s["spc.ramReg[1]"])
  for i=0,2 do b(s["spc.timer"..i..".target"]) end
  for i=0,2 do b(s["spc.timer"..i..".output"]) end
  for a=0,65535 do b(emu.read(a, emu.memType.spcRam, false)) end
  for a=0,127 do b(emu.read(a, emu.memType.spcDspRegisters, false)) end
  return table.concat(t)
end
"""


PARAMS = bytes([1, 1, 2, 3, 0, 1, 2, 1, 2, 1, 1, 3, 0, 1, 2, 3, 1, 3, 3, 0, 1, 3, 0, 3, 3, 3, 1])  # E0-FA, as N-SPC
SONG_START = bytes([0x1C, 0x5D, 0xF5])  # ASL A ; MOV X,A ; MOV A,table+1+X


def spc_file(raw: bytes, title: str, port0: int, seconds: int, fade: int) -> bytes:
    """SPC v0.30: header (registers, ID666 text), 64 KB RAM with the I/O registers, DSP registers, IPL area."""
    pc_lo, pc_hi, a, x, y, ps, sp = raw[:7]
    ctl, dsp_addr = raw[7:9]
    ports, ram_regs, targets, counters = bytes([port0]) + raw[10:13], raw[13:15], raw[15:18], raw[18:21]
    ram = bytearray(raw[21:21 + 0x10000])
    dsp = raw[21 + 0x10000:21 + 0x10000 + 128]
    ram[0xF0:0x100] = bytes([0x0A, ctl, dsp_addr, dsp[dsp_addr & 0x7F]]) + ports + ram_regs + targets + counters
    head = bytearray(0x100)
    head[:33] = b"SNES-SPC700 Sound File Data v0.30"
    head[0x21:0x25] = bytes([26, 26, 26, 30])
    head[0x25:0x2C] = bytes([pc_lo, pc_hi, a, x, y, ps, sp])
    head[0x2E:0x2E + len(title)] = title.encode("ascii")
    head[0x4E:0x4E + 16] = b"Yokoyama Sangoku"  # game title (ID666, 32 bytes, ASCII)
    head[0xA9:0xAC] = b"%03d" % min(seconds, 999)  # ID666 text: play length (s), fade (ms)
    head[0xAC:0xB1] = b"%05d" % (fade * 1000)
    return bytes(head) + bytes(ram) + dsp + bytes(64) + ram[0xFFC0:0x10000]


def word(ram: bytes, a: int) -> int:
    return ram[a] | ram[a + 1] << 8


def track(ram: bytes, params: bytes, a: int) -> tuple[int, list[tuple[int, int]]]:
    """Ticks of one track up to its 00, and its tempo commands as (tick, tempo)."""
    t = dur = 0
    tempos = []
    for _ in range(0x4000):
        c = ram[a]
        a += 1
        if c == 0:
            return t, tempos
        if c < 0x80:  # length, then an optional duration/velocity byte
            dur = c
            a += ram[a] < 0x80
        elif c < 0xE0:
            t += dur
        elif c == 0xEF:  # subroutine: address, count - 1
            st, sc = track(ram, params, word(ram, a))
            for i in range(ram[a + 2] + 1):
                tempos += [(t + i * st + x, v) for x, v in sc]
            t += (ram[a + 2] + 1) * st
            a += 3
        elif c == 0xFF:
            raise ValueError(f"FF at {a - 1:04X}")
        else:
            if c in (0xE7, 0xE8):  # tempo, tempo fade (taken at once)
                tempos.append((t, ram[a + params[c - 0xE0] - 1]))
            a += params[c - 0xE0]
    raise ValueError("track without end")


def song_length(ram: bytes, n: int) -> tuple[int, float, float | None]:
    """(block list address, intro seconds, loop seconds or None when the song ends) of song n."""
    i = ram.find(SONG_START)
    table = word(ram, i + 3) - 1
    lbase = ram.find(PARAMS)
    params = ram[lbase:lbase + 31]  # E0-FE
    blocks = word(ram, table + 2 * n)
    a, tempo, counter, times = blocks, 0x20, 0, []
    for _ in range(0x200):
        v = word(ram, a)
        if v >= 0x100:
            ticks, tempos = track(ram, params, word(ram, v))
            secs = last = 0
            for x, tv in tempos + [(ticks, None)]:
                secs += (x - last) * 256 / (500 * tempo)
                last, tempo = x, tv or tempo
            times.append((a, secs))
            a += 2
        elif v == 0:
            return blocks, sum(t for _, t in times), None
        else:
            target = word(ram, a + 2)
            if v >= 0x80:  # forever
                return (blocks, sum(t for x, t in times if x < target), sum(t for x, t in times if x >= target))
            counter = v if counter == 0 else counter - 1
            a = target if counter else a + 4
    raise ValueError("block list without end")


def render(spc: str, seconds: float, fade: int) -> array.array:
    """Stereo 16-bit samples of the SPC played by libgme for seconds, then faded out over fade seconds."""
    gme = ctypes.CDLL(LIBGME)
    gme.gme_open_file.restype = ctypes.c_char_p
    emu = ctypes.c_void_p()
    err = gme.gme_open_file(spc.encode(), ctypes.byref(emu), RATE)
    if err:
        raise RuntimeError(err.decode())
    gme.gme_start_track(emu, 0)
    gme.gme_set_fade(emu, int(seconds * 1000))
    out = array.array("h")
    n = int((seconds + fade) * RATE) * 2
    buf = (ctypes.c_short * n)()
    gme.gme_play(emu, n, buf)
    out.extend(buf)
    gme.gme_delete(emu)
    return out


def dump(rom: str, bank: int, path: str) -> None:
    patch = [(SONG_OPERAND, b"\x01")] + [(o, bytes([bank])) for o in SET_OPERANDS]
    run = {"patch": patch, "steps": STEPS, "shot": SHOT, "read": []}
    (raw,), = replay(rom, BOOT, SAVE_AT, [run], extra_lua=SPC_LUA)
    with open(path, "wb") as f:
        f.write(raw)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=ROM)
    ap.add_argument("--loops", type=int, default=2, help="times a looping song is played before the fade")
    ap.add_argument("--fade", type=int, default=10, help="fade-out seconds")
    ap.add_argument("--dump", type=int, help=argparse.SUPPRESS)  # child: dump the state of one set (bank)
    args = ap.parse_args()
    out = os.path.join(GAME, "output", "music")
    os.makedirs(out, exist_ok=True)
    if args.dump is not None:
        dump(args.rom, args.dump, os.path.join(out, f"{args.dump:02X}.raw"))
        return

    def child(bank: int) -> None:  # one Mesen per process
        subprocess.run([sys.executable, __file__, "--rom", args.rom, "--dump", str(bank)], timeout=300,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    with ThreadPoolExecutor(len(SETS)) as pool:
        list(pool.map(child, SETS))
    with open(os.path.join(GAME, "data", "music_zophar.tsv"), encoding="utf-8") as f:
        ext = {(r.pop("音樂組"), r.pop("曲號")): r for r in csv.DictReader(f, delimiter="\t")}
    blank = dict.fromkeys(next(iter(ext.values())), "")
    rows = []
    for bank in SETS:
        raw_path = os.path.join(out, f"{bank:02X}.raw")
        with open(raw_path, "rb") as f:
            raw = f.read()
        os.remove(raw_path)
        ram = raw[21:21 + 0x10000]
        seen = {}
        for n in range(1, 0x19):
            try:
                blocks, intro, loop = song_length(ram, n)
            except (ValueError, IndexError):
                continue
            if blocks in seen:  # another number for a song already listed
                continue
            seen[blocks] = n
            key = f"{bank:02X}-{n:02X}"
            use, basis = USES.get(key, ("unknown", ""))
            kind = "bgm" if loop is not None else "jingle"
            name = f"{key}_{kind}_{use}"
            seconds = intro + args.loops * loop if loop is not None else intro + 1
            spc = os.path.join(out, f"{name}.spc")
            fade = args.fade if loop is not None else 0
            with open(spc, "wb") as f:
                f.write(spc_file(raw, f"Set {bank:02X} song {n:02X}", n, round(seconds), fade))
            pcm = render(spc, seconds, fade)
            loud = [sum(v * v for v in pcm[i:i + RATE * 2:8]) / (RATE // 4) > 300 ** 2
                    for i in range(0, len(pcm), RATE * 2)]
            if sum(loud) < 3:  # silent, or a blip shorter than 3 seconds
                os.remove(spc)
                continue
            with tempfile.NamedTemporaryFile(suffix=".wav") as w:
                with wave.open(w.name, "wb") as wav:
                    wav.setnchannels(2)
                    wav.setsampwidth(2)
                    wav.setframerate(RATE)
                    wav.writeframes(pcm.tobytes())
                for ext_, codec in (("ogg", ["-c:a", "libopus", "-b:a", "96k"]),
                                    ("mp3", ["-c:a", "libmp3lame", "-q:a", "2"])):  # both from the WAV
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", w.name, *codec,
                                    os.path.join(out, f"{name}.{ext_}")], check=True)
            ends = "循環 ✅ code+emu（樂段清單的跳躍）" if loop is not None else "結束 ✅ code（樂段清單 0000）"
            rows.append({"編號": key, "種類": kind, "檔名": name, "用途": use, "前奏秒": f"{intro:.2f}",
                         "循環秒": "" if loop is None else f"{loop:.2f}", "依據": "；".join(filter(None, [ends, basis])),
                         "樂段清單": f"{blocks:04X}", **ext.get((f"{bank:02X}", f"{n:02X}"), blank)})
            print(f"{name}: intro {intro:.2f} s, loop {'-' if loop is None else f'{loop:.2f} s'}")
    with open(os.path.join(out, "music.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} songs -> {out}")


if __name__ == "__main__":
    main()
