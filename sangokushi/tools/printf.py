"""printf capture for tools/replay.py runs of スーパー三國志 (tools/printf_trace.py with this game's printf).

The game formats its screen text with a C printf at $C2:16DC (format: 3-byte pointer at sp+4; arguments: 16-bit
bank-0 pointer at sp+8; %d takes 2 bytes, %ld 4, %s a 4-byte pointer). Pass LUA as replay(..., extra_lua=LUA);
every run then appends the calls it saw (cleared at each savestate load) and parse() reads them back.

    rows = parse(results[k][-1])   # [(format address, [args...]), ...]; a %s argument is ("s", address)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools"))
import printf_trace

PRINTF = 0xC216DC

LUA = printf_trace.lua(PRINTF, fmt_at=4, va_at=8, va_size=2, max_calls=100000) + """
function EXTRA_RESET() PF_RESET() end
function EXTRA_SHOT() return PF_SHOT() end
"""


def parse(blob: bytes) -> list[tuple[int, list]]:
    return [(c["fmt"], [("s", a.addr) if isinstance(a, printf_trace.Str) else a for a in c["args"]])
            for c in printf_trace.parse(blob)]
