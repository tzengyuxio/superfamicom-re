"""KOEI's LZ decompressor of the mid-90s SFC titles (天翔記 $C0:F194, 項劉記 $C0:A2AB), shared.

The decoder uses a 0x15D-byte block of lookup tables that sits right before the routine and is byte-for-byte
the same in every game seen so far, so find_tables() locates it by content. find_pointer_tables() then looks
for the game's tables of 3-byte pointers (HiROM or LoROM) to the streams.

    tables = find_tables(rom)            # file offset of the table block, or -1
    out, end = decompress(rom, p, tables)

Usage: .venv/bin/python tools/koei_lz.py ROM   # report table block, routine and pointer tables
"""
import sys

# Offsets inside the table block
LEN_VALUE, LEN_BITS, LEN_SHIFT = 0x00, 0x40, 0x7F
NEAR_OFFSET, NEAR_BITS = 0x87, 0x147
FAR_SHIFT, FAR_BITS = 0x150, 0x155
ROUTINE = 0x15D  # the decoder starts right after the tables
# The table block as found in 天翔記 (0xF037) and 項劉記 (0xA14E)
BLOCK = bytes.fromhex(
    "ff1fff3fff7fffff08090a0b0c0d0e0f040404040505050506060606070707070202020202020202020202020202020203030303"
    "0303030303030303030303031a181414101010100c0c0c0c0c0c0c0c080808080808080808080808080808080404040404040404"
    "0404040404040404040404040404040404040404040404040408080c0c0c0c000000000000000001010101010101010202020202"
    "020202030303030303030304040404050505050606060607070707080809090a0a0b0b0c0c0d0d0e0e0f0f101011111212131314"
    "14151516161717181819191a1a1b1b1c1c1d1d1e1e1f1f202122232425262728292a2b2c2d2e2f303132333435363738393a3b3c"
    "3d3e3f404142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f606162636465666768696a6b6c6d6e6f70"
    "7172737475767778797a7b7c7d7e7f0e0e101212121414141414140a0806040216181a1c1e")


def find_tables(rom: bytes) -> int:
    """File offset of the table block; -1 if the game doesn't have it."""
    return rom.find(BLOCK)


def decompress(rom: bytes, p: int, tables: int, limit: int = 1 << 20) -> tuple[bytes, int]:
    """(output, end offset of the stream) of the stream at file offset p.

    A 16-bit bit window W is filled from little-endian words of the stream; flag bytes and literals
    are read from the same pointer in between. Flag bits (MSB first): 1 = literal byte; 0 = copy
    length + 1 bytes from distance + 1 back, with a prefix-coded length and distance taken from W.
    The length value 0xFF ends the stream.
    """
    t = tables
    w = n = avail = 0

    def take(bits: int) -> None:  # shift `bits` new bits into W
        nonlocal w, n, avail, p
        w = (w << bits) & 0xFFFF
        if avail >= bits:
            avail -= bits
            w |= (n >> avail) & ((1 << bits) - 1)
        else:
            need = bits - avail
            w |= ((n & ((1 << avail) - 1)) << need) & 0xFFFF
            n = rom[p] | rom[p + 1] << 8
            p += 2
            avail = 16 - need
            w |= (n >> avail) & ((1 << need) - 1)

    take(16)
    out = bytearray()
    while len(out) < limit:
        flags = rom[p]
        p += 1
        for k in range(8):
            if flags >> (7 - k) & 1:
                out.append(rom[p])
                p += 1
                continue
            if w & 0x8000:
                length = 1
            else:
                y = w >> 9
                if y == 0:
                    length = (w >> 2) | 0x80
                    if length == 0xFF:
                        return bytes(out), p
                elif y < 8:
                    length = (w >> 1) >> (rom[t + LEN_SHIFT + y] // 2)
                else:
                    length = rom[t + LEN_VALUE + y]
                take(rom[t + LEN_BITS + y] // 2)
            if (w << 1) & 0xFFFF < 0x6000:
                y = ((w << 2) & 0xFFFF) >> 8
                dist, bits = rom[t + NEAR_OFFSET + y], rom[t + NEAR_BITS + (y >> 4)] // 2
            else:
                y = (w >> 12) & 7
                dist, bits = ((w & 0x0FFF) | 0x1000) >> (rom[t + FAR_SHIFT + y] // 2), rom[t + FAR_BITS + y] // 2
            take(bits)
            start = len(out) - dist - 1
            if start < 0:
                raise ValueError(f"copy before the start of the output at stream offset {p:#x}")
            for i in range(length + 1):
                out.append(out[start + i])
    return bytes(out), p


def _packed(rom: bytes, p: int, nxt: int, tables: int) -> bool:
    """The stream at p decodes and ends where the next one starts (streams are stored back to back)."""
    try:
        return 0 <= nxt - decompress(rom, p, tables, limit=1 << 16)[1] < 4
    except (ValueError, IndexError):
        return False


def cpu_to_file(v: int, hirom: bool) -> int:
    """File offset of CPU address v (HiROM: bank $C0-$FF; LoROM: $8000-$FFFF of any bank); -1 if not ROM."""
    if hirom:
        return v & 0x3FFFFF if v >> 16 >= 0xC0 else -1
    return (v >> 16 & 0x7F) * 0x8000 + (v & 0x7FFF) if v & 0x8000 and v >> 16 & 0x7F < 0x7E else -1


def find_pointer_tables(rom: bytes, tables: int, hirom: bool = True, min_run: int = 32) -> list[tuple[int, int]]:
    """[(file offset, entry count)] of every run of at least min_run 3-byte pointers into the ROM
    whose streams are packed back to back, judged on 16 samples. Some entries can be uncompressed
    data (天翔記 17, 18, 20, 102-105) and the first may be junk (項劉記 0). A game can have more than one table
    (天翔記: 0x1F95A4 and 0x10DEA0)."""
    def ptr(i: int) -> int:
        f = cpu_to_file(int.from_bytes(rom[i:i + 3], "little"), hirom)
        return f if f < len(rom) else -1

    found = []
    for phase in range(3):
        i = phase
        while i + 3 <= len(rom):
            start = i
            while i + 3 <= len(rom) and ptr(i) >= 0:
                i += 3
            count = (i - start) // 3
            if count >= min_run:
                ks = sorted({1 + (count - 2) * j // 15 for j in range(16)})
                if sum(_packed(rom, ptr(start + 3 * k), ptr(start + 3 * k + 3), tables) for k in ks) * 2 >= len(ks):
                    found.append((start, count))
            i = max(i, start + 3)
    return sorted(found)


def main() -> None:
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from triage import header, load_rom
    rom = load_rom(sys.argv[1])
    t = find_tables(rom)
    if t < 0:
        print("no KOEI LZ tables")
        return
    hirom = header(rom)["kind"] == "HiROM"
    found = ", ".join(f"{at:#x} ({count} entries)" for at, count in find_pointer_tables(rom, t, hirom))
    print(f"tables {t:#x}, routine at file {t + ROUTINE:#x}"
          f", pointer tables: {found or 'none'}")


if __name__ == "__main__":
    main()
