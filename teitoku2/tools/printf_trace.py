"""vsprintf trace for tools/replay.py: Lua that records every call of the game's vsprintf (fmt address, the
arguments as the format string reads them, and the text it wrote), and the parser of what it hands back.

vsprintf(dst, fmt, va) takes 4-byte stack arguments (dst at sp+4, fmt at sp+8, va at sp+12); in va a %d / %u /
%x / %c takes 2 bytes, %ld 4 bytes and %s 4 bytes (a 24-bit pointer). The Lua walks the format (two-byte codes,
ESC K / ESC H / ESC C x, where x may be a %c) to read each argument when the call is made, and reads dst at the return address
(taken from the stack and hooked once per call site).
"""

LUA = r"""
local PF_MAX = @MAX@
local pf, pending, hooked = {}, nil, {}
local function rd(a) return emu.read(a, emu.memType.snesMemory, false) end
local function hx(t, b) t[#t + 1] = string.format("%02x", b) end
local function cstr(t, p, n)
  local s = {}
  for i = 0, n - 1 do local c = rd(p + i); if c == 0 then break end; s[#s + 1] = c end
  hx(t, #s)
  for _, c in ipairs(s) do hx(t, c) end
end
local function finish()
  if pending == nil then return end
  local t = pending.t
  cstr(t, pending.dst, 160)
  pf[#pf + 1] = table.concat(t)
  pending = nil
end
local function on_return() finish() end
function PF_RESET() pf = {}; pending = nil end
function PF_SHOT() finish(); return table.concat(pf) end
emu.addMemoryCallback(function()
  finish()
  if #pf >= PF_MAX then return end
  local sp = emu.getState()["cpu.sp"]
  local function a24(o) return rd(sp + o) | rd(sp + o + 1) << 8 | rd(sp + o + 2) << 16 end
  local dst, fmt, va = a24(4), a24(8), a24(12)
  local ret = a24(1) + 1
  if not hooked[ret] then hooked[ret] = true; emu.addMemoryCallback(on_return, emu.callbackType.exec, ret) end
  local t, args, off, i = {}, {}, 0, 0
  for k = 0, 2 do hx(t, fmt >> (8 * (2 - k)) & 255) end
  while i < 200 do
    local c = rd(fmt + i)
    if c == 0 then break end
    if c == 0x1B then
      i = i + ((rd(fmt + i + 1) == 0x43 and rd(fmt + i + 2) ~= 0x25) and 3 or 2)  -- ESC C x; ESC C %c
    elseif (c >= 0x81 and c <= 0x9F) or c >= 0xE0 then
      i = i + 2
    elseif c == 0x25 then
      i = i + 1
      local long = false
      while true do
        c = rd(fmt + i)
        if c == 0x6C then long = true end
        if not (c == 0x2D or c == 0x2B or c == 0x20 or c == 0x30 or c == 0x23 or c == 0x2E or c == 0x6C
                or (c >= 0x31 and c <= 0x39) or (c == 0x30)) then break end
        i = i + 1
      end
      i = i + 1
      if c == 0x73 then
        local p = rd(va + off) | rd(va + off + 1) << 8 | rd(va + off + 2) << 16
        local u = {"73"}; cstr(u, p, 60); args[#args + 1] = table.concat(u); off = off + 4
      elseif c ~= 0x25 then
        local n = long and 4 or 2
        local u = {long and "6c" or "64"}
        for k = n - 1, 0, -1 do hx(u, rd(va + off + k)) end
        args[#args + 1] = table.concat(u); off = off + n
      end
    else
      i = i + 1
    end
  end
  hx(t, #args)
  for _, a in ipairs(args) do t[#t + 1] = a end
  pending = {t = t, dst = dst}
end, emu.callbackType.exec, @VSPRINTF@)
"""


def lua(vsprintf: int, max_calls: int = 3000) -> str:
    """The trace Lua; call PF_RESET() from EXTRA_RESET and append PF_SHOT() to EXTRA_SHOT."""
    return LUA.replace("@MAX@", str(max_calls)).replace("@VSPRINTF@", str(vsprintf))


def parse(raw: bytes) -> list[dict]:
    """PF_SHOT() bytes -> [{"fmt": CPU address, "args": [int | bytes], "out": bytes}]. A %d argument is the
    unsigned 16-bit value (32-bit for %ld); a %s argument the bytes of the string."""
    out, i = [], 0
    while i < len(raw):
        fmt = int.from_bytes(raw[i:i + 3], "big")
        n = raw[i + 3]
        i += 4
        args = []
        for _ in range(n):
            kind = raw[i]
            if kind == 0x73:
                k = raw[i + 1]
                args.append(bytes(raw[i + 2:i + 2 + k]))
                i += 2 + k
            else:
                size = 4 if kind == 0x6C else 2
                args.append(int.from_bytes(raw[i + 1:i + 1 + size], "big"))
                i += 1 + size
        k = raw[i]
        out.append({"fmt": fmt, "args": args, "out": bytes(raw[i + 1:i + 1 + k])})
        i += 1 + k
    return out


def signed16(v: int) -> int:
    return v - 0x10000 if v >= 0x8000 else v
