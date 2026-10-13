#!/usr/bin/env python3
"""Screenshot the province screen with marked values, to read off which byte is which field (needs Mesen 2).

Scenario 1, 織田信長: before the 尾張 (province 23) screen is drawn (frame ~3807), every field of its WRAM record
($7E:DC00 + 8 + 32 * 23) is overwritten with its own offset: 2-byte fields with 1000 + offset, 1-byte fields with
the offset. On the screenshot each number then names its byte, e.g. 金 1004 -> +4, 民忠 16 -> +16.

Usage: .venv/bin/python bushou/tools/province_probe.py OUT.png [--rom ROM]
"""
import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
from mesen import Mesen
from PIL import Image
from replay import presses
from rom import DEFAULT_ROM, PROVINCE_SIZE, PROVINCE_START, WRAM

PROVINCE = 23
WORDS, BYTES = (4, 6, 8, 11, 14, 17, 24, 26), (10, 13, 16, 28, 29)
STEPS = ("w900 start:10 w300 a:10 w200 a:10 w200 a:10 w200 a:10 w200 up:10 w60 a:10 w200 a:10 w200 a:10 w200 "
         "a:10 w300 a:10 w900")
POKE_AT, SHOT_AT = 3700, 4200
LUA = """
local ev={%(ev)s}
local writes={%(writes)s}
local f=0
emu.addEventCallback(function()
  local inp={}
  for _,p in ipairs(ev) do if f>=p[1] and f<p[1]+p[3] then inp[p[2]]=true end end
  emu.setInput(inp,0)
end, emu.eventType.inputPolled)
emu.addEventCallback(function()
  f=f+1
  if f==%(poke)d then for _,w in ipairs(writes) do emu.write(w[1], w[2], emu.memType.snesMemory) end end
  if f==%(shot)d then shot("probe"); emu.breakExecution() end
end, emu.eventType.endFrame)
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="國畫面欄位探測截圖")
    ap.add_argument("out")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    base = 0x7E0000 + WRAM + PROVINCE_START + PROVINCE_SIZE * PROVINCE
    writes = [(base + k, (1000 + k) & 0xFF) for k in WORDS] + [(base + k + 1, (1000 + k) >> 8) for k in WORDS]
    writes += [(base + k, k) for k in BYTES]
    lua = LUA % {"ev": ",".join(f'{{{f},"{b}",{h}}}' for f, b, h in presses(STEPS, 10)),
                 "writes": ",".join(f"{{{a},{v}}}" for a, v in writes), "poke": POKE_AT, "shot": SHOT_AT}
    with Mesen(args.rom) as m:
        m.run(lua, 600)
        png = m.screenshots()["probe"]
    Image.open(io.BytesIO(png)).resize((512, 448), Image.NEAREST).save(args.out)
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
