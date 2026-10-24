"""Task-scoped idle-sleep request, only on AC power; never override battery policy."""
import ctypes
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class PowerStatus(ctypes.Structure):
    _fields_ = [('ac', ctypes.c_byte), ('flags', ctypes.c_byte), ('percent', ctypes.c_byte),
                ('system', ctypes.c_byte), ('remaining', ctypes.c_ulong), ('full', ctypes.c_ulong)]


def main():
    kernel = ctypes.windll.kernel32
    kernel.SetThreadExecutionState.argtypes = [ctypes.c_ulong]
    kernel.SetThreadExecutionState.restype = ctypes.c_ulong
    end = time.time() + 12 * 3600
    previous = None
    try:
        while time.time() < end and not (ROOT/'keep-awake.stop').exists():
            status = PowerStatus()
            valid = kernel.GetSystemPowerStatus(ctypes.byref(status))
            required = bool(valid and status.ac == 1)
            result = kernel.SetThreadExecutionState(0x80000001 if required else 0x80000000)
            if not result:
                raise ctypes.WinError()
            if required != previous:
                (ROOT/'keep-awake-status.json').write_text(json.dumps({
                    'recorded_at':time.time(), 'prevent_idle_sleep_on_ac':required,
                    'battery_percent':status.percent, 'expires_at':end}), encoding='utf8')
                previous = required
            time.sleep(20)
    finally:
        kernel.SetThreadExecutionState(0x80000000)


if __name__ == '__main__':
    main()
