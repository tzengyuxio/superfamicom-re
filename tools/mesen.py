"""Run a ROM headless in Mesen 2 through MesenCore.dylib (ctypes), with an optional Lua script.

Mirrors Mesen's own --testrunner (UI/Utilities/TestRunner.cs), which cannot start here because
its Avalonia UI needs a display. A script hands control back with emu.breakExecution(): the
emulator pauses with the game still loaded, so its emu.log() output and any memory can be read,
and run() / resume() continue from there. emu.stop() ends the emulation for good.

    with Mesen(rom_path) as m:
        m.run(lua_source, timeout=60)
        log = m.log()
        wram = m.memory(SNES_WRAM)
"""
import ctypes
import os
import re
import tempfile
import time
import zipfile

# Prepended to every script: shot(tag) logs a screenshot that screenshots() decodes
LUA_PRELUDE = """
function shot(tag)
  local png = emu.takeScreenshot()
  emu.log("PNG " .. tag .. " " .. png:gsub(".", function(c) return string.format("%02x", c:byte()) end))
end
"""
CORE = os.path.expanduser("~/Library/Application Support/Mesen2/MesenCore.dylib")

# Core/Shared/MemoryType.h
SNES_MEMORY, SNES_PRG_ROM, SNES_WRAM, SNES_SRAM, SNES_VRAM, SNES_OAM, SNES_CGRAM = 0, 14, 15, 16, 17, 18, 19
# Core/Shared/SettingTypes.h EmulationFlags
MAXIMUM_SPEED, CONSOLE_MODE = 0x04, 0x10


# Core/Shared/SettingTypes.h, passed by value to SetSnesConfig
class _KeyMapping(ctypes.Structure):
    _fields_ = [("keys", ctypes.c_uint16 * 23), ("custom", ctypes.c_uint16 * 100)]


class _ControllerConfig(ctypes.Structure):
    _fields_ = [("mappings", _KeyMapping * 4), ("turbo_speed", ctypes.c_uint32), ("type", ctypes.c_int32)]


class _SnesConfig(ctypes.Structure):
    _fields_ = [
        ("port1", _ControllerConfig), ("port2", _ControllerConfig),
        ("port1_sub", _ControllerConfig * 4), ("port2_sub", _ControllerConfig * 4),
        ("region", ctypes.c_int32),
        ("flags", ctypes.c_bool * 9),  # AllowInvalidInput ... ForceFixedResolution
        ("overscan", ctypes.c_uint32 * 4),
        ("interpolation", ctypes.c_int32),
        ("channel_volumes", ctypes.c_uint32 * 8),
        ("random_power_on", ctypes.c_bool), ("strict_mappings", ctypes.c_bool),
        ("ram_power_on", ctypes.c_int32),
        ("spc_clock_adjust", ctypes.c_int32),
        ("extra_before_nmi", ctypes.c_uint32), ("extra_after_nmi", ctypes.c_uint32),
        ("gsu_clock", ctypes.c_uint32),
        ("bsx_date", ctypes.c_int64),
    ]


SNES_CONTROLLER, RAM_ALL_ZEROS = 1, 1


class Mesen:
    def __init__(self, rom_path: str, home: str | None = None):
        self._tmp = tempfile.TemporaryDirectory(prefix="mesen-")
        if rom_path.lower().endswith(".zip"):  # Mesen reads zips, but give it a plain file to be sure
            with zipfile.ZipFile(rom_path) as z:
                name = next(n for n in z.namelist() if n.lower().endswith((".sfc", ".smc", ".nes")))
                rom_path = z.extract(name, self._tmp.name)
        self.core = ctypes.CDLL(CORE)
        c = self.core
        c.InitializeEmu.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_bool] * 4
        c.LoadRom.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        c.LoadRom.restype = ctypes.c_bool
        c.SetEmulationFlag.argtypes = [ctypes.c_uint32, ctypes.c_bool]
        c.LoadScript.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32]
        c.LoadScript.restype = ctypes.c_int32
        c.GetScriptLog.argtypes = [ctypes.c_int32, ctypes.c_char_p, ctypes.c_uint32]
        c.IsRunning.restype = ctypes.c_bool
        c.IsExecutionStopped.restype = ctypes.c_bool
        c.GetStopCode.restype = ctypes.c_int32
        c.GetMemorySize.argtypes = [ctypes.c_int32]
        c.GetMemorySize.restype = ctypes.c_int32
        c.GetMemoryState.argtypes = [ctypes.c_int32, ctypes.c_char_p]
        c.InitDll()
        c.InitializeEmu((home or self._tmp.name).encode(), None, None, True, True, True, True)
        cfg = _SnesConfig()  # one standard controller in port 1, deterministic power-on RAM
        cfg.port1.type = SNES_CONTROLLER
        cfg.channel_volumes[:] = [100] * 8
        cfg.ram_power_on = RAM_ALL_ZEROS
        cfg.gsu_clock = 100
        cfg.bsx_date = -1
        c.SetSnesConfig(cfg)
        c.Pause()
        c.SetEmulationFlag(CONSOLE_MODE, True)
        if not c.LoadRom(rom_path.encode(), b""):
            raise RuntimeError(f"Mesen could not load {rom_path}")
        c.InitializeDebugger()
        self.script_id = -1

    def run(self, lua: str, timeout: float = 60, name: str = "script.lua") -> None:
        """Load the Lua script and run at maximum speed until it calls emu.breakExecution()."""
        c = self.core
        self.script_id = c.LoadScript(name.encode(), self._tmp.name.encode(), (LUA_PRELUDE + lua).encode(), self.script_id)
        c.SetEmulationFlag(MAXIMUM_SPEED, True)
        c.Resume()
        self._wait(timeout)

    def resume(self, timeout: float = 60) -> None:
        """Continue after a break until the script breaks again."""
        self.core.ResumeExecution()
        self._wait(timeout)

    def _wait(self, timeout: float) -> None:
        c = self.core
        time.sleep(0.05)
        end = time.time() + timeout
        while time.time() < end:
            if c.IsExecutionStopped():
                return
            if not c.IsRunning():
                raise RuntimeError(f"emulation stopped (code {c.GetStopCode()})")
            time.sleep(0.02)
        raise TimeoutError(f"script did not break within {timeout}s\n{self.log()[-2000:]}")

    def log(self, size: int = 1 << 22) -> str:
        buf = ctypes.create_string_buffer(size)
        self.core.GetScriptLog(self.script_id, buf, size)
        return buf.value.decode("utf-8", errors="replace")

    def screenshots(self) -> dict[str, bytes]:
        """PNG files logged by shot(tag), by tag."""
        return {m[1]: bytes.fromhex(m[2]) for m in re.finditer(r"^PNG (\S+) ([0-9a-f]+)$", self.log(), re.MULTILINE)}

    def memory(self, mem_type: int) -> bytes:
        size = self.core.GetMemorySize(mem_type)
        buf = ctypes.create_string_buffer(size)
        self.core.GetMemoryState(mem_type, buf)
        return buf.raw

    def close(self) -> None:
        self.core.Stop()
        self.core.Release()
        self._tmp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
