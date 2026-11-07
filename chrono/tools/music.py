"""Dump the music as SPC files and render them to OGG and MP3, with the lengths read from the song data.

Usage: .venv/bin/python chrono/tools/music.py [--rom ROM] [--loops 2] [--fade 10] [--songs 01,18]
       → chrono/output/music/NN_<kind>_<use>.spc / .ogg (Opus 96k) / .mp3 (LAME VBR -q:a 2), music.csv
       (NN = song number; kind bgm = loops, jingle = ends; use unknown when not known; ~/.claude/re-common.md §10)

The 65816 asks for a song with $1E00 = 10, $1E01 = song and JSL $C7:0004, which uploads that song's sequence (pointer
table $C7:0D18, 3 bytes per song, 00-50; at the pointer: length word, then the data that goes to SPC $2000) and its
instruments. Every song is made from the title: the first play command (song 30 at frame 98) gets its song number
swapped (WRAM write in Lua, so modified), and the SPC700 state is taken at the first key-on (DSP $4C written by MOV
$F3,A at SPC $02BA) with the SPC700 PC put back on that instruction, so the SPC file starts with the song's first
notes. The game's NMI vector jumps to RAM ($00:FF10 JML $00:0500), so replay.py hooks $00:0500.

Song data at SPC $2000 (Akao, the version of FF6): base address of the data in ROM, end address, 8 track pointers,
the same 8 again (a pointer equal to the end address is an unused track), then the tracks (an address a in the data is SPC (a - base) & $FFFF + $2024: data can cross a bank). Events: 00-C3 note (op / 14 =
pitch, 12 tie, 13 rest; op % 14 = length from the table at SPC $1DB3), C4-FF commands with the parameter lengths at
SPC $15CC (handlers at $1554): E2 n loop start (n + 1 times), E3 loop end, F5 n addr leave the loop on pass n, F6 addr
jump, F0 tempo, EB-EF / FE / FF end of track. A tick passes when the tempo (F0 n -> n + n * 20 / 256, $1722) added
at every timer 0 step ($FA = $2A: 5.25 ms) carries out of 8 bits ($037A). 前奏秒 and 循環秒 come from that, counted
from the first note (the SPC file starts there). The driver waits for the timer 0 counter ($029C MOV Y,$FD ; BEQ)
and takes one step however many have passed, so a busy song plays slower than its score: the loop is measured on
the libgme waveform (measure_loop) near the score's length, and the intro is scaled by the same ratio. music.csv adds the [EXT] columns of data/music_zophar.tsv.
"""
import argparse
import csv
import os
import re
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(os.path.dirname(GAME), "tools"))
from paths import ORIGINAL
from replay import replay
from spc import RAM, RATE, STATE_LUA, encode, loud_seconds, render, spc_file

ROM = os.path.join(ORIGINAL, "Chrono Trigger (Japan).zip")
SONG_TABLE = 0x070D18      # ROM offset of $C7:0D18
SONGS = range(0x01, 0x51)  # 00 is an empty song
NMI = 0x000500
BOOT = "w60"               # the title starts its song at frame 98
STEPS = "w200"
SHOT = 150
MAILBOX = 0x1FFFF          # WRAM byte ($7F:FFFF) that tells the Lua which song to start
LENGTHS = 0x15CC           # SPC: parameter lengths of C4-FF
DURATIONS = 0x1DB3         # SPC: note lengths
TIMER = 0x2A * 125e-6      # timer 0 step (s)
SLOWER = 0.03              # the most the playback was found slower than the score (see measure_loop)
WINDOW = 8                 # seconds of envelope compared
MATCH = 0.9                # envelope correlation needed to take the measured loop
MAX_SECONDS = 20 * 60
HALT = {0xEB, 0xEC, 0xED, 0xEE, 0xEF, 0xFE, 0xFF}
# Songs whose scene is known: "NN" -> (use, basis). Songs not listed take their Zophar title (data/music_zophar.tsv)
USES: dict[str, tuple[str, str]] = {}


def title_use(titles: str) -> str:
    """Kebab-case use from the first Zophar title, without "(Looped)" and the like."""
    t = re.sub(r"\s*\(.*?\)", "", titles.split(" / ")[0]).lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")

LUA = STATE_LUA + """
local armed, pending, state = false, false, "00"
emu.addMemoryCallback(function(a, v)
  if v == 0x10 and not armed then
    armed = true
    emu.write(0x1E01, emu.read(MAILBOX, emu.memType.snesWorkRam), emu.memType.snesWorkRam)
    pending = true
  end
end, emu.callbackType.write, 0x001E00, 0x001E00)
emu.addMemoryCallback(function(a, v)
  if pending and emu.getState()["spc.dspReg"] == 0x4C and v ~= 0 then
    pending = false; state = SPC_STATE()
  end
end, emu.callbackType.write, 0x00F3, 0x00F3, emu.cpuType.spc, emu.memType.spcMemory)
function EXTRA_RESET() armed=false; pending=false; state="00" end
function EXTRA_SHOT() return state end
""".replace("MAILBOX", str(MAILBOX))


def rewind(raw: bytes) -> bytes:
    """Put the SPC700 PC back on the MOV $F3,A that wrote the key-on (the state is taken right after it)."""
    pc = raw[0] | raw[1] << 8
    if raw[RAM + pc - 2:RAM + pc] != b"\xc4\xf3":
        raise ValueError(f"key-on not written by MOV $F3,A (PC {pc:04X})")
    return bytes([(pc - 2) & 255, (pc - 2) >> 8]) + raw[2:]


def tracks(ram: bytes) -> list[tuple[int, int | None, tuple[int, int] | None, list[tuple[int, int]]]]:
    """Per distinct track: (ticks to the end or to the loop jump, ticks to the first note, (loop start, loop end) or
    None, tempo commands as (tick, parameter)). A track that neither ends nor loops is left out."""
    lengths = ram[LENGTHS:LENGTHS + 60]
    dur = ram[DURATIONS:DURATIONS + 14]
    w = lambda i: ram[i] | ram[i + 1] << 8
    base = w(0x2000)
    spc = lambda p: ((p - base) & 0xFFFF) + 0x2024  # data may cross a bank boundary
    out = []
    for k in range(8):
        p = w(0x2004 + 2 * k)
        if spc(p) >= spc(w(0x2002)) or p in [w(0x2004 + 2 * j) for j in range(k)]:  # unused (= end of data), or shared
            continue
        i, t, stack, seen, tempos, first, loop = spc(p), 0, [], {}, [], None, None
        for _ in range(100000):
            seen.setdefault((i, str(stack)), t)
            op = ram[i]
            if op < 0xC4:
                if first is None and op // 14 < 12:
                    first = t
                t += dur[op % 14]
                i += 1
                continue
            arg = ram[i + 1:i + 1 + lengths[op - 0xC4]]
            nxt = i + 1 + len(arg)
            if op in HALT:
                loop = False
                break
            if op == 0xF0:
                tempos.append((t, arg[0]))
            elif op == 0xE2:
                stack.append([arg[0] + 1, nxt, 0])  # times, start, passes done
            elif op == 0xE3:
                stack[-1][2] += 1
                if stack[-1][2] < stack[-1][0]:
                    nxt = stack[-1][1]
                else:
                    stack.pop()
            elif op == 0xF5:
                if stack and stack[-1][2] + 1 == arg[0]:
                    stack.pop()
                    nxt = spc(arg[1] | arg[2] << 8)
            elif op == 0xF6:
                nxt = spc(arg[0] | arg[1] << 8)
                if (nxt, str(stack)) in seen:
                    loop = (seen[(nxt, str(stack))], t)
                    break
            i = nxt
        if loop is not None:
            out.append((t, first, loop or None, tempos))
    return out


def seconds(tempos: list[tuple[int, int]], t0: int, t1: int) -> float:
    """Seconds from tick t0 to tick t1 under the tempo commands."""
    tempo, s, last = None, 0.0, 0
    for x, v in sorted(tempos) + [(t1, None)]:
        x = min(x, t1)
        if tempo and x > t0:
            s += (x - max(last, t0)) * 256 * TIMER / tempo
        last = max(last, x)
        if v is not None:
            tempo = v + (v * 20 >> 8)
    return s


def song_length(ram: bytes) -> tuple[float, float | None]:
    """(intro seconds from the first note, loop seconds or None when the song ends)."""
    ts = tracks(ram)
    tempos = sorted(e for *_, ev in ts for e in ev)
    lead = min(f for _, f, _, _ in ts if f is not None)
    loops = [lp for _, _, lp, _ in ts if lp]
    if loops:
        s0, s1 = max(loops, key=lambda x: x[1] - x[0])
        return seconds(tempos, lead, s0), seconds(tempos, s0, s1)
    return seconds(tempos, lead, max(t for t, *_ in ts)), None


def envelope(pcm) -> list[int]:
    """Energy of every 10 ms (left channel, every 2nd sample)."""
    step = RATE // 100
    return [sum(v * v for v in pcm[2 * i:2 * (i + step):4]) for i in range(0, len(pcm) // 2 - step, step)]


def corr(x: list[int], y: list[int]) -> float:
    mx, my = sum(x) / len(x), sum(y) / len(y)
    num = sum((p - mx) * (q - my) for p, q in zip(x, y))
    den = (sum((p - mx) ** 2 for p in x) * sum((q - my) ** 2 for q in y)) ** 0.5
    return num / den if den else 0.0


def measure_loop(spc: str, intro: float, loop: float) -> tuple[float, float]:
    """(loop seconds, match) where the energy envelope after the intro repeats best, searched from 0.5 % shorter to
    SLOWER longer than the loop computed from the score (the driver drops timer steps it is too busy to take)."""
    pcm = render(spc, intro + 2 * loop * (1 + SLOWER) + WINDOW + 1, 0)
    env = envelope(pcm)
    w = int(min(WINDOW, loop * 0.8) * 100)
    i0 = int((intro + 0.5) * 100)
    ref = env[i0:i0 + w]
    found = [(corr(ref, env[i0 + d:i0 + d + w]), d / 100)
             for d in range(int(loop * 99.5), int(loop * 100 * (1 + SLOWER)) + 1) if i0 + d + w <= len(env)]
    match, seconds_ = max(found)
    return seconds_, match


def rom_song(rom: str, n: int) -> bytes:
    """Song n as the ROM keeps it (what goes to SPC $2000)."""
    with zipfile.ZipFile(rom) as z:
        data = z.read(z.namelist()[0])
    p = int.from_bytes(data[SONG_TABLE + 3 * n:SONG_TABLE + 3 * n + 3], "little") - 0xC00000
    return data[p + 2:p + 2 + int.from_bytes(data[p:p + 2], "little")]


def dump(rom: str, songs: list[int]) -> dict[int, bytes]:
    runs = [{"patch": [], "wram": [(MAILBOX, bytes([n]))], "steps": STEPS, "shot": SHOT, "read": []} for n in songs]
    res = replay(rom, BOOT, int(BOOT[1:]), runs, extra_lua=LUA, nmi=NMI)
    return {n: raw for n, (raw,) in zip(songs, res) if len(raw) > 1}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=ROM)
    ap.add_argument("--loops", type=int, default=2, help="times a looping song is played before the fade")
    ap.add_argument("--fade", type=int, default=10, help="fade-out seconds")
    ap.add_argument("--songs", help="hex numbers, comma separated (default 01-50)")
    args = ap.parse_args()
    songs = [int(x, 16) for x in args.songs.split(",")] if args.songs else list(SONGS)
    out = os.path.join(GAME, "output", "music")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(GAME, "data", "music_zophar.tsv"), encoding="utf-8") as f:
        ext = {r.pop("曲號"): r for r in csv.DictReader(f, delimiter="\t")}
    blank = dict.fromkeys(next(iter(ext.values())), "")
    raws = dump(args.rom, songs)
    rows = []
    for n in songs:
        key = f"{n:02X}"
        if n not in raws:
            print(f"{key}: no key-on (silent)")
            continue
        raw = rewind(raws[n])
        seq = rom_song(args.rom, n)
        if raw[RAM + 0x2000:RAM + 0x2000 + len(seq)] != seq:
            raise SystemExit(f"{key}: SPC $2000 is not song {key} of the ROM")
        intro, loop = song_length(raw[RAM:RAM + 0x10000])
        if intro + (loop or 0) > MAX_SECONDS:
            raise SystemExit(f"{key}: {intro:.0f} + {loop} s, the song data was not read right")
        use, basis = USES.get(key, ("unknown", ""))
        if key not in USES and key in ext:
            use, basis = title_use(ext[key]["[EXT]Zophar 曲名"]), "用途 🟡 Zophar 曲名（reference）"
        kind = "bgm" if loop is not None else "jingle"
        name = f"{key}_{kind}_{use}"
        with tempfile.NamedTemporaryFile(suffix=".spc") as tmp:
            tmp.write(spc_file(raw, f"Song {key}", "Chrono Trigger", 999, 0))
            tmp.flush()
            if loop is None:
                ends = "結束 ✅ code（EB 等結束碼）；長度多留 3%＋1 秒（實際播放比樂譜慢）"
            else:
                measured, match = measure_loop(tmp.name, intro, loop)
                if match >= MATCH:
                    ends = (f"循環 ✅ code+emu（F6 跳躍；長度量自 libgme 波形，比樂譜算的 {loop:.2f} 秒"
                            f"{'長' if measured >= loop else '短'} {abs(measured / loop - 1) * 100:.1f}%，相關 {match:.2f}）")
                    intro, loop = intro * measured / loop, measured
                else:
                    ends = f"循環 🟡 code（F6 跳躍；樂譜算的長度，實際可能稍慢；波形比對不出，相關 {match:.2f}）"
        length = intro + args.loops * loop if loop is not None else intro * (1 + SLOWER) + 1
        fade = args.fade if loop is not None else 0
        data = spc_file(raw, f"Song {key}", "Chrono Trigger", round(length), fade)
        with tempfile.NamedTemporaryFile(suffix=".spc") as tmp:
            tmp.write(data)
            tmp.flush()
            pcm = render(tmp.name, length, fade)
        if loud_seconds(pcm) < 1:
            print(f"{key}: silent")
            continue
        with open(os.path.join(out, f"{name}.spc"), "wb") as f:
            f.write(data)
        encode(pcm, os.path.join(out, name))
        rows.append({"編號": key, "種類": kind, "檔名": name, "用途": use, "前奏秒": f"{intro:.2f}",
                     "循環秒": "" if loop is None else f"{loop:.2f}", "依據": "；".join(filter(None, [ends, basis])),
                     **ext.get(key, blank)})
        print(f"{name}: intro {intro:.2f} s, loop {'-' if loop is None else f'{loop:.2f} s'}")
    with open(os.path.join(out, "music.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} songs -> {out}")


if __name__ == "__main__":
    main()
