"""printf capture for tools/replay.py runs of スーパー三國志.

The game formats its screen text with a C printf at $C2:16DC (format: 3-byte pointer at sp+4; arguments: 16-bit
bank-0 pointer at sp+8; %d takes 2 bytes, %ld 4, %s a 4-byte pointer). LUA hooks it and keeps one record per
call: the format address and the arguments (numbers, and %s pointers). Pass it as replay(..., extra_lua=LUA); every
run then appends the records it saw (EXTRA_RESET clears them at each savestate load) and parse() reads them back.

    rows = parse(results[k][-1])   # [(format address, [args...]), ...]; a %s argument is ("s", address)
"""

PRINTF = 0xC216DC

LUA = r"""
local pf_buf = {}
local function pf_rd(a) return emu.read(a, emu.memType.snesMemory, false) end
emu.addMemoryCallback(function()
  local sp = emu.getState()["cpu.sp"]
  local fmt = pf_rd(sp + 4) | pf_rd(sp + 5) << 8 | pf_rd(sp + 6) << 16
  local va = pf_rd(sp + 8) | pf_rd(sp + 9) << 8
  local args, off, i = {}, 0, 0
  while i < 300 do
    local c = pf_rd(fmt + i)
    if c == 0 then break end
    if (c >= 0x81 and c <= 0x9F) or c >= 0xE0 then
      i = i + 2
    elseif c == 0x1B then
      i = i + 2
    elseif c == 0x25 then
      i = i + 1
      local long = false
      while true do
        c = pf_rd(fmt + i)
        if c == 0x6C then long = true end
        local flag = c == 0x2D or c == 0x2B or c == 0x20 or c == 0x23 or c == 0x2E or c == 0x6C
        if not (flag or (c >= 0x30 and c <= 0x39)) then break end
        i = i + 1
      end
      i = i + 1
      if c == 0x73 then
        local p = pf_rd(va + off) | pf_rd(va + off + 1) << 8 | pf_rd(va + off + 2) << 16
        args[#args + 1] = string.format("s%X", p); off = off + 4
      elseif c ~= 0x25 then
        local n = long and 4 or 2
        local v = 0
        for k = n - 1, 0, -1 do v = v * 256 + pf_rd(va + off + k) end
        args[#args + 1] = string.format("d%d", v); off = off + n
      end
    else
      i = i + 1
    end
  end
  pf_buf[#pf_buf + 1] = string.format("%X:", fmt) .. table.concat(args, ",")
end, emu.callbackType.exec, 0xC216DC)
function EXTRA_RESET() pf_buf = {} end
function EXTRA_SHOT()
  local s = table.concat(pf_buf, ";")
  if s == "" then return "00" end
  return (s:gsub(".", function(ch) return string.format("%02x", ch:byte()) end))
end
"""


def parse(blob: bytes) -> list[tuple[int, list]]:
    text = blob.decode("ascii").strip("\0")
    out = []
    for rec in filter(None, text.split(";")):
        fmt, _, rest = rec.partition(":")
        args = [("s", int(a[1:], 16)) if a[0] == "s" else int(a[1:]) for a in filter(None, rest.split(","))]
        out.append((int(fmt, 16), args))
    return out
