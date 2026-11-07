"""SPC700 state dumps from Mesen and what is made from them: SPC files, libgme rendering, OGG + MP3
(~/.claude/re-common.md §10). Taken from yokoyama/tools/music.py when the second game needed it.

    raw = <the hex string of STATE_LUA's SPC_STATE() as bytes>   # e.g. returned through replay.py's EXTRA_SHOT
    data = spc_file(raw, "Song 01", "Chrono Trigger", seconds=120, fade=10)
    pcm = render(path, 120, 10); encode(pcm, "out/01_bgm_title")      # -> .ogg (Opus 96k) and .mp3 (LAME VBR)

raw layout: SPC700 PC (2), A, X, Y, PSW, SP, timer enable bits, DSP address, ports $F4-$F7 (4, what the CPU wrote),
$F8-$F9, timer targets (3), timer outputs (3), 64 KB RAM, 128 DSP registers.
"""
import array
import ctypes
import subprocess
import tempfile
import wave

LIBGME = "/opt/homebrew/opt/game-music-emu/lib/libgme.dylib"
RATE = 32000
RAM = 21  # offset of the 64 KB RAM in raw

# Lua: SPC_STATE() returns the state above as a hex string
STATE_LUA = """
function SPC_STATE()
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


def spc_file(raw: bytes, title: str, game: str, seconds: int, fade: int, port0: int | None = None) -> bytes:
    """SPC v0.30: header (registers, ID666 text), 64 KB RAM with the I/O registers, DSP registers, IPL area.
    port0 replaces what the SPC700 reads at $F4 (default: what the CPU last wrote)."""
    pc_lo, pc_hi, a, x, y, ps, sp = raw[:7]
    ctl, dsp_addr = raw[7:9]
    ports = bytes([raw[9] if port0 is None else port0]) + raw[10:13]
    ram_regs, targets, counters = raw[13:15], raw[15:18], raw[18:21]
    ram = bytearray(raw[RAM:RAM + 0x10000])
    dsp = raw[RAM + 0x10000:RAM + 0x10000 + 128]
    ram[0xF0:0x100] = bytes([0x0A, ctl, dsp_addr, dsp[dsp_addr & 0x7F]]) + ports + ram_regs + targets + counters
    head = bytearray(0x100)
    head[:33] = b"SNES-SPC700 Sound File Data v0.30"
    head[0x21:0x25] = bytes([26, 26, 26, 30])
    head[0x25:0x2C] = bytes([pc_lo, pc_hi, a, x, y, ps, sp])
    head[0x2E:0x2E + min(len(title), 32)] = title.encode("ascii")[:32]
    head[0x4E:0x4E + min(len(game), 32)] = game.encode("ascii")[:32]
    head[0xA9:0xAC] = b"%03d" % min(seconds, 999)  # ID666 text: play length (s), fade (ms)
    head[0xAC:0xB1] = b"%05d" % (fade * 1000)
    return bytes(head) + bytes(ram) + dsp + bytes(64) + ram[0xFFC0:0x10000]


def render(spc: str, seconds: float, fade: int) -> array.array:
    """Stereo 16-bit samples (RATE Hz) of the SPC played by libgme for seconds, then faded out over fade seconds."""
    gme = ctypes.CDLL(LIBGME)
    gme.gme_open_file.restype = ctypes.c_char_p
    emu = ctypes.c_void_p()
    err = gme.gme_open_file(spc.encode(), ctypes.byref(emu), RATE)
    if err:
        raise RuntimeError(err.decode())
    gme.gme_start_track(emu, 0)
    gme.gme_set_fade(emu, int(seconds * 1000))
    n = int((seconds + fade) * RATE) * 2
    buf = (ctypes.c_short * n)()
    gme.gme_play(emu, n, buf)
    gme.gme_delete(emu)
    out = array.array("h")
    out.extend(buf)
    return out


def loud_seconds(pcm: array.array, level: int = 300) -> int:
    """Number of 1-second stretches louder than level (RMS)."""
    return sum(sum(v * v for v in pcm[i:i + RATE * 2:8]) / (RATE // 4) > level ** 2 for i in range(0, len(pcm), RATE * 2))


def encode(pcm: array.array, base: str) -> None:
    """base.ogg (Opus 96k) and base.mp3 (LAME VBR -q:a 2), both from one WAV."""
    with tempfile.NamedTemporaryFile(suffix=".wav") as w:
        with wave.open(w.name, "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(RATE)
            wav.writeframes(pcm.tobytes())
        for ext, codec in (("ogg", ["-c:a", "libopus", "-b:a", "96k"]), ("mp3", ["-c:a", "libmp3lame", "-q:a", "2"])):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", w.name, *codec, f"{base}.{ext}"], check=True)
