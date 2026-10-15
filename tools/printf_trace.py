"""printf / vsprintf trace for tools/replay.py: Lua that records every call of a game's formatter (format address,
the arguments as the format string reads them, and optionally the text it wrote), and the parser of the result.

KOEI's C formatters take their arguments on the stack. Pass where they are (offsets from sp at the hooked entry):
fmt_at = the 24-bit format pointer, va_at = the va_list pointer (va_size 2 = a bank-0 pointer, 3 = 24-bit) and,
for vsprintf, dst_at = the output buffer, which is read when the call returns (the return address is taken from
the stack and hooked once per call site). In va a %d / %u / %x / %c takes 2 bytes, %ld 4 and %s 4 (a 24-bit
pointer). The format walk skips two-byte characters (0x81-0x9F, 0xE0-) and escapes: ESC + 1 byte, or with
esc_c ESC C x (x may be a %c argument).

    lua = printf_trace.lua(0xC216DC, fmt_at=4, va_at=8, va_size=2) + '''
    function EXTRA_RESET() PF_RESET() end
    function EXTRA_SHOT() return PF_SHOT() end
    '''
    results = replay(rom, boot, save, runs, extra_lua=lua)
    calls = printf_trace.parse(results[k][-1])   # [{"fmt": address, "args": [int | Str], "out": bytes}]

A %d argument is the unsigned 16-bit value (32-bit for %ld); a %s argument is a Str: the bytes of the string
(up to 60) with .addr, the pointer it was read from. "out" is empty without dst_at.
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
  if pending.dst then cstr(t, pending.dst, 160) else hx(t, 0) end
  pf[#pf + 1] = table.concat(t)
  pending = nil
end
local function on_return() finish() end
function PF_RESET() pf = {}; pending = nil end
function PF_SHOT() finish(); return table.concat(pf) .. "00" end  -- the 00 keeps the field when nothing was seen
emu.addMemoryCallback(function()
  finish()
  if #pf >= PF_MAX then return end
  local sp = emu.getState()["cpu.sp"]
  local function a24(o) return rd(sp + o) | rd(sp + o + 1) << 8 | rd(sp + o + 2) << 16 end
  local fmt = a24(@FMT_AT@)
  local va = @VA_SIZE@ == 3 and a24(@VA_AT@) or (rd(sp + @VA_AT@) | rd(sp + @VA_AT@ + 1) << 8)
  local dst = nil
  if @DST_AT@ >= 0 then
    dst = a24(@DST_AT@)
    local ret = a24(1) + 1
    if not hooked[ret] then hooked[ret] = true; emu.addMemoryCallback(on_return, emu.callbackType.exec, ret) end
  end
  local t, args, off, i = {}, {}, 0, 0
  for k = 0, 2 do hx(t, fmt >> (8 * (2 - k)) & 255) end
  while i < 300 do
    local c = rd(fmt + i)
    if c == 0 then break end
    if c == 0x1B then
      i = i + ((@ESC_C@ and rd(fmt + i + 1) == 0x43 and rd(fmt + i + 2) ~= 0x25) and 3 or 2)  -- ESC C x; ESC C %c
    elseif (c >= 0x81 and c <= 0x9F) or c >= 0xE0 then
      i = i + 2
    elseif c == 0x25 then
      i = i + 1
      local long = false
      while true do
        c = rd(fmt + i)
        if c == 0x6C then long = true end
        if not (c == 0x2D or c == 0x2B or c == 0x20 or c == 0x23 or c == 0x2E or c == 0x6C
                or (c >= 0x30 and c <= 0x39)) then break end
        i = i + 1
      end
      i = i + 1
      if c == 0x73 then
        local p = rd(va + off) | rd(va + off + 1) << 8 | rd(va + off + 2) << 16
        local u = {"73"}
        for k = 0, 2 do hx(u, p >> (8 * (2 - k)) & 255) end
        cstr(u, p, 60); args[#args + 1] = table.concat(u); off = off + 4
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
end, emu.callbackType.exec, @ENTRY@)
"""


class Str(bytes):
    """A %s argument: the string's bytes, with .addr the 24-bit pointer it was read from."""
    addr: int

    def __new__(cls, data: bytes, addr: int):
        s = super().__new__(cls, data)
        s.addr = addr
        return s


def lua(entry: int, fmt_at: int, va_at: int, va_size: int = 3, dst_at: int | None = None, esc_c: bool = False,
        max_calls: int = 3000) -> str:
    """The trace Lua; call PF_RESET() from EXTRA_RESET and return PF_SHOT() from EXTRA_SHOT."""
    subst = {"MAX": max_calls, "ENTRY": entry, "FMT_AT": fmt_at, "VA_AT": va_at, "VA_SIZE": va_size,
             "DST_AT": -1 if dst_at is None else dst_at, "ESC_C": "true" if esc_c else "false"}
    out = LUA
    for k, v in subst.items():
        out = out.replace(f"@{k}@", str(v))
    return out


def parse(raw: bytes) -> list[dict]:
    """PF_SHOT() bytes -> [{"fmt": CPU address, "args": [int | Str], "out": bytes}]."""
    out, i = [], 0
    while i + 4 < len(raw):  # the trailing 00 of PF_SHOT
        fmt = int.from_bytes(raw[i:i + 3], "big")
        n = raw[i + 3]
        i += 4
        args = []
        for _ in range(n):
            kind = raw[i]
            if kind == 0x73:
                addr = int.from_bytes(raw[i + 1:i + 4], "big")
                k = raw[i + 4]
                args.append(Str(raw[i + 5:i + 5 + k], addr))
                i += 5 + k
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
