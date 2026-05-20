"""Real WGFMU backend bound to Keysight B1530A ``wgfmu.dll`` via ctypes.

This module intentionally keeps the **import** side-effect free: missing DLLs
or being on a non-Windows host must NOT break ``import fefetlab``.  The
underlying library is only resolved when :class:`RealWgfmuBackend` is actually
instantiated or when :meth:`open_session` is called, depending on which
attribute is first touched.

The C API names (95 functions) come from the Keysight B1530A User Guide
(``B1500/B1500手册/keysight-b1530a-series-user-guide.pdf``).  The selected
subset below is exactly what :class:`WgfmuSmokeRunner`, ``WgfmuIVSweepRunner``
and ``WgfmuWakeupRunner`` need.
"""

from __future__ import annotations

import ctypes
import os
import platform
from ctypes import c_char_p, c_double, c_int, POINTER
from pathlib import Path
from typing import Optional

import pandas as pd

from .backend import WgfmuBackend


# ---- Keysight WGFMU constants (verified against WGFMU.cs from B1530A
# Instrument Library Sample Programs A04.00.2024.0540) ----------------------
WGFMU_NO_ERROR = 0

# WGFMU.setOperationMode (offset 2000)
OPERATION_MODE_MAP = {
    "DC": 2000,
    "FASTIV": 2001,
    "PG": 2002,
    "SMU": 2003,
}

# WGFMU.setForceVoltageRange (offset 3000)
FORCE_VOLTAGE_RANGE_MAP = {
    "AUTO": 3000,
    "3V": 3001,
    "5V": 3002,
    "10V_NEGATIVE": 3003,
    "10V_POSITIVE": 3004,
}

# WGFMU.setMeasureMode (offset 4000)
MEASURE_MODE_MAP = {
    "VOLTAGE": 4000,
    "CURRENT": 4001,
}

# WGFMU.setMeasureVoltageRange (offset 5000)
MEASURE_VOLTAGE_RANGE_MAP = {
    "5V": 5001,
    "10V": 5002,
}

# WGFMU.setMeasureCurrentRange (offset 6000)
MEASURE_CURRENT_RANGE_MAP = {
    "1UA": 6001,
    "10UA": 6002,
    "100UA": 6003,
    "1MA": 6004,
    "10MA": 6005,
}

# WGFMU.setMeasureEnabled (offset 7000)
MEASURE_ENABLED_MAP = {
    "DISABLE": 7000,
    "ENABLE": 7001,
}

# WGFMU.setMeasureEvent (offset 12000)
MEASURE_EVENT_DATA_MAP = {
    "averaged": 12000,
    "raw": 12001,
}

# WGFMU.treatWarningsAsErrors / setWarningLevel (offset 1000)
WARNING_LEVEL_MAP = {
    "OFF": 1000,
    "SEVERE": 1001,
    "NORMAL": 1002,
    "INFORMATION": 1003,
}


class WgfmuLibraryError(RuntimeError):
    """Raised when a WGFMU C API call returns a non-zero status."""

    def __init__(self, func: str, status: int, summary: str = ""):
        self.func = func
        self.status = status
        self.summary = summary
        msg = f"{func} failed with status={status}"
        if summary:
            msg += f": {summary}"
        super().__init__(msg)


def _default_dll_search_paths() -> list[str]:
    env_path = os.environ.get("WGFMU_DLL_PATH")
    candidates: list[str] = []
    if env_path:
        candidates.append(env_path)
    # Standard Keysight install locations on Windows.
    # System32 / SysWOW64 are where the modern installer drops wgfmu.dll
    # (verified on 椰椰 2026-05-20 setup: B1530A Instrument Library
    # A04.00.2024.0540 → C:\Windows\System32\wgfmu.dll for 64-bit).
    candidates += [
        r"C:\Windows\System32\wgfmu.dll",
        r"C:\Program Files\Keysight\B1530A\bin\wgfmu.dll",
        r"C:\Program Files\Keysight\B1500A\WGFMU\bin\wgfmu.dll",
        r"C:\Program Files (x86)\Keysight\B1500A\WGFMU\bin\wgfmu.dll",
        r"C:\Program Files\Agilent\B1500A\WGFMU\bin\wgfmu.dll",
        # Legacy Agilent EasyEXPERT path (32-bit only, will fail under 64-bit Python)
        r"C:\Program Files (x86)\Agilent\B1500\EasyEXPERT\Utilities\WGFMU\bin\wgfmu.dll",
        "wgfmu.dll",
    ]
    return candidates


def _load_wgfmu_dll(explicit_path: Optional[str] = None) -> "ctypes.CDLL":
    """Locate and load ``wgfmu.dll``.

    Raises ``OSError`` with a helpful message if the library cannot be found.
    """
    if platform.system() != "Windows":
        raise OSError(
            "RealWgfmuBackend requires Windows (Keysight wgfmu.dll). "
            f"Detected platform: {platform.system()!r}. "
            "Use DummyWgfmuBackend for development on other OSes."
        )
    paths = [explicit_path] if explicit_path else []
    paths += _default_dll_search_paths()
    tried: list[str] = []
    for p in paths:
        if not p:
            continue
        try:
            return ctypes.WinDLL(p)  # type: ignore[attr-defined]
        except OSError as exc:
            tried.append(f"  {p}: {exc}")
    raise OSError(
        "Could not load wgfmu.dll. Set the WGFMU_DLL_PATH environment "
        "variable or pass dll_path=. Tried:\n" + "\n".join(tried)
    )


class RealWgfmuBackend(WgfmuBackend):
    """ctypes-based backend bound to Keysight WGFMU2 library.

    Instantiation does NOT load the DLL automatically — call :meth:`load`
    explicitly (or it will be loaded lazily on the first session call).
    This keeps unit tests on Linux importable.
    """

    def __init__(self, dll_path: Optional[str] = None):
        super().__init__()
        self._dll_path = dll_path
        self._dll: Optional["ctypes.CDLL"] = None
        self._error_buffer_size = 1024

    # ------------------------------------------------------------------ lifecycle
    def load(self) -> None:
        """Resolve and bind the WGFMU DLL. Idempotent."""
        if self._dll is not None:
            return
        dll = _load_wgfmu_dll(self._dll_path)
        # Bind signatures defensively — every WGFMU_* function returns int.
        def _bind(name: str, argtypes):
            try:
                fn = getattr(dll, name)
            except AttributeError as exc:
                raise OSError(
                    f"wgfmu.dll is missing symbol {name!r}; is it the right version?"
                ) from exc
            fn.argtypes = argtypes
            fn.restype = c_int
            return fn

        self._fn = {
            "openSession": _bind("WGFMU_openSession", [c_char_p]),
            "closeSession": _bind("WGFMU_closeSession", []),
            "initialize": _bind("WGFMU_initialize", []),
            "clear": _bind("WGFMU_clear", []),
            "setTimeout": _bind("WGFMU_setTimeout", [c_double]),
            "getChannelIdSize": _bind("WGFMU_getChannelIdSize", [POINTER(c_int)]),
            "getChannelIds": _bind("WGFMU_getChannelIds", [POINTER(c_int), POINTER(c_int)]),
            "getErrorSummarySize": _bind("WGFMU_getErrorSummarySize", [POINTER(c_int)]),
            "getErrorSummary": _bind("WGFMU_getErrorSummary", [c_char_p, POINTER(c_int)]),
            "getWarningSummarySize": _bind("WGFMU_getWarningSummarySize", [POINTER(c_int)]),
            "getWarningSummary": _bind("WGFMU_getWarningSummary", [c_char_p, POINTER(c_int)]),
            "treatWarningsAsErrors": _bind("WGFMU_treatWarningsAsErrors", [c_int]),
            "createPattern": _bind("WGFMU_createPattern", [c_char_p, c_double]),
            "addVector": _bind("WGFMU_addVector", [c_char_p, c_double, c_double]),
            "setMeasureEvent": _bind(
                "WGFMU_setMeasureEvent",
                [c_char_p, c_char_p, c_double, c_int, c_double, c_double, c_int],
            ),
            "addSequence": _bind("WGFMU_addSequence", [c_int, c_char_p, c_double]),
            "exportAscii": _bind("WGFMU_exportAscii", [c_char_p]),
            "setOperationMode": _bind("WGFMU_setOperationMode", [c_int, c_int]),
            "setForceVoltageRange": _bind("WGFMU_setForceVoltageRange", [c_int, c_int]),
            "setMeasureEnabled": _bind("WGFMU_setMeasureEnabled", [c_int, c_int]),
            "setMeasureMode": _bind("WGFMU_setMeasureMode", [c_int, c_int]),
            "setMeasureCurrentRange": _bind("WGFMU_setMeasureCurrentRange", [c_int, c_int]),
            "setMeasureVoltageRange": _bind("WGFMU_setMeasureVoltageRange", [c_int, c_int]),
            "connect": _bind("WGFMU_connect", [c_int]),
            "disconnect": _bind("WGFMU_disconnect", [c_int]),
            "execute": _bind("WGFMU_execute", []),
            "waitUntilCompleted": _bind("WGFMU_waitUntilCompleted", []),
            "getMeasureValueSize": _bind(
                "WGFMU_getMeasureValueSize", [c_int, POINTER(c_int), POINTER(c_int)]
            ),
            "getMeasureValues": _bind(
                "WGFMU_getMeasureValues",
                [c_int, c_int, POINTER(c_int), POINTER(c_double), POINTER(c_double)],
            ),
        }
        self._dll = dll

    def _ensure_loaded(self) -> None:
        if self._dll is None:
            self.load()

    def _check(self, func: str, status: int) -> None:
        if status == WGFMU_NO_ERROR:
            return
        # Best-effort: surface the error summary the instrument gives us
        try:
            summary = self.get_error_summary()
        except Exception:  # pragma: no cover - defensive
            summary = ""
        raise WgfmuLibraryError(func, status, summary)

    # ------------------------------------------------------------------ session
    def open_session(self, resource: str):
        self._ensure_loaded()
        status = self._fn["openSession"](resource.encode("ascii"))
        # If a session is already open (CONTEXT_ERROR=-3 with that message),
        # close it transparently and retry.  This makes notebook re-runs and
        # mid-cell experiments resilient.
        if status == -3:
            try:
                self._fn["closeSession"]()
            except Exception:
                pass
            status = self._fn["openSession"](resource.encode("ascii"))
        self._check("openSession", status)
        self.session_opened = True
        return status

    def close_session(self):
        if self._dll is None:
            return 0
        status = self._fn["closeSession"]()
        self.session_opened = False
        return status

    def initialize(self):
        self._ensure_loaded()
        status = self._fn["initialize"]()
        self._check("initialize", status)
        return status

    def clear(self):
        self._ensure_loaded()
        status = self._fn["clear"]()
        self._check("clear", status)
        return status

    def set_timeout(self, timeout_s: float):
        self._ensure_loaded()
        status = self._fn["setTimeout"](c_double(timeout_s))
        self._check("setTimeout", status)
        return status

    def get_channel_ids(self) -> list[int]:
        self._ensure_loaded()
        size = c_int(0)
        self._check("getChannelIdSize", self._fn["getChannelIdSize"](ctypes.byref(size)))
        if size.value == 0:
            return []
        arr = (c_int * size.value)()
        sz = c_int(size.value)
        self._check(
            "getChannelIds",
            self._fn["getChannelIds"](arr, ctypes.byref(sz)),
        )
        return [int(arr[i]) for i in range(sz.value)]

    def _read_string(self, size_fn_key: str, get_fn_key: str) -> str:
        if self._dll is None:
            return ""
        size = c_int(0)
        if self._fn[size_fn_key](ctypes.byref(size)) != 0:
            return ""
        if size.value <= 0:
            return ""
        buf = ctypes.create_string_buffer(size.value + 1)
        sz = c_int(size.value + 1)
        if self._fn[get_fn_key](buf, ctypes.byref(sz)) != 0:
            return ""
        return buf.value.decode("ascii", errors="replace")

    def get_error_summary(self) -> str:
        return self._read_string("getErrorSummarySize", "getErrorSummary")

    def get_warning_summary(self) -> str:
        return self._read_string("getWarningSummarySize", "getWarningSummary")

    def treat_warnings_as_errors(self, level: str):
        self._ensure_loaded()
        level_code = WARNING_LEVEL_MAP.get(level.upper(), WARNING_LEVEL_MAP["SEVERE"])
        status = self._fn["treatWarningsAsErrors"](c_int(level_code))
        self._check("treatWarningsAsErrors", status)
        return status

    # ------------------------------------------------------------------ offline setup
    def create_pattern(self, pattern: str, init_v: float):
        self._ensure_loaded()
        status = self._fn["createPattern"](pattern.encode("ascii"), c_double(init_v))
        self._check("createPattern", status)
        return status

    def add_vector(self, pattern: str, dtime_s: float, voltage: float):
        self._ensure_loaded()
        status = self._fn["addVector"](
            pattern.encode("ascii"), c_double(dtime_s), c_double(voltage)
        )
        self._check("addVector", status)
        return status

    def set_measure_event(
        self,
        pattern: str,
        event: str,
        time_s: float,
        points: int,
        interval_s: float,
        average_s: float,
        raw_data_mode: str,
    ):
        self._ensure_loaded()
        mode_code = MEASURE_EVENT_DATA_MAP.get(raw_data_mode.lower(), 0)
        status = self._fn["setMeasureEvent"](
            pattern.encode("ascii"),
            event.encode("ascii"),
            c_double(time_s),
            c_int(points),
            c_double(interval_s),
            c_double(average_s),
            c_int(mode_code),
        )
        self._check("setMeasureEvent", status)
        return status

    def add_sequence(self, chan_id: int, pattern: str, count: int):
        self._ensure_loaded()
        status = self._fn["addSequence"](
            c_int(chan_id), pattern.encode("ascii"), c_double(count)
        )
        self._check("addSequence", status)
        return status

    def export_ascii(self, filepath: str):
        self._ensure_loaded()
        status = self._fn["exportAscii"](filepath.encode("ascii"))
        self._check("exportAscii", status)
        return status

    # ------------------------------------------------------------------ online setup
    def set_operation_mode(self, chan_id: int, mode: str):
        self._ensure_loaded()
        code = OPERATION_MODE_MAP.get(mode.upper(), OPERATION_MODE_MAP["FASTIV"])
        self._check(
            "setOperationMode",
            self._fn["setOperationMode"](c_int(chan_id), c_int(code)),
        )

    def set_force_voltage_range(self, chan_id: int, rng: str):
        self._ensure_loaded()
        code = FORCE_VOLTAGE_RANGE_MAP.get(rng.upper(), FORCE_VOLTAGE_RANGE_MAP["AUTO"])
        self._check(
            "setForceVoltageRange",
            self._fn["setForceVoltageRange"](c_int(chan_id), c_int(code)),
        )

    def set_measure_enabled(self, chan_id: int, enabled: bool):
        self._ensure_loaded()
        code = MEASURE_ENABLED_MAP["ENABLE"] if enabled else MEASURE_ENABLED_MAP["DISABLE"]
        self._check(
            "setMeasureEnabled",
            self._fn["setMeasureEnabled"](c_int(chan_id), c_int(code)),
        )

    def set_measure_mode(self, chan_id: int, mode: str):
        self._ensure_loaded()
        code = MEASURE_MODE_MAP.get(mode.upper(), MEASURE_MODE_MAP["CURRENT"])
        self._check(
            "setMeasureMode",
            self._fn["setMeasureMode"](c_int(chan_id), c_int(code)),
        )

    def set_measure_current_range(self, chan_id: int, rng: str):
        self._ensure_loaded()
        code = MEASURE_CURRENT_RANGE_MAP.get(rng.upper(), MEASURE_CURRENT_RANGE_MAP["1MA"])
        self._check(
            "setMeasureCurrentRange",
            self._fn["setMeasureCurrentRange"](c_int(chan_id), c_int(code)),
        )

    def set_measure_voltage_range(self, chan_id: int, rng: str):
        self._ensure_loaded()
        code = MEASURE_VOLTAGE_RANGE_MAP.get(rng.upper(), MEASURE_VOLTAGE_RANGE_MAP["10V"])
        self._check(
            "setMeasureVoltageRange",
            self._fn["setMeasureVoltageRange"](c_int(chan_id), c_int(code)),
        )

    def connect(self, chan_id: int):
        self._ensure_loaded()
        self._check("connect", self._fn["connect"](c_int(chan_id)))

    def disconnect(self, chan_id: int):
        if self._dll is None:
            return
        try:
            self._check("disconnect", self._fn["disconnect"](c_int(chan_id)))
        except WgfmuLibraryError:
            # disconnect failures during teardown shouldn't mask real errors
            pass

    # ------------------------------------------------------------------ execute
    def execute(self):
        self._ensure_loaded()
        self._check("execute", self._fn["execute"]())

    def wait_until_completed(self):
        self._ensure_loaded()
        self._check("waitUntilCompleted", self._fn["waitUntilCompleted"]())

    # ------------------------------------------------------------------ result
    def get_measure_value_size(self, chan_id: int) -> tuple[int, int]:
        self._ensure_loaded()
        completed = c_int(0)
        total = c_int(0)
        self._check(
            "getMeasureValueSize",
            self._fn["getMeasureValueSize"](
                c_int(chan_id), ctypes.byref(completed), ctypes.byref(total)
            ),
        )
        return int(completed.value), int(total.value)

    def get_measure_values(self, chan_id: int) -> pd.DataFrame:
        self._ensure_loaded()
        completed, _total = self.get_measure_value_size(chan_id)
        if completed <= 0:
            return pd.DataFrame({"time_s": [], "value": []})
        sz = c_int(completed)
        times = (c_double * completed)()
        values = (c_double * completed)()
        self._check(
            "getMeasureValues",
            self._fn["getMeasureValues"](
                c_int(chan_id), c_int(0), ctypes.byref(sz), times, values
            ),
        )
        n = sz.value
        return pd.DataFrame({
            "time_s": [float(times[i]) for i in range(n)],
            "value": [float(values[i]) for i in range(n)],
        })


__all__ = [
    "RealWgfmuBackend",
    "WgfmuLibraryError",
    "OPERATION_MODE_MAP",
    "FORCE_VOLTAGE_RANGE_MAP",
    "MEASURE_MODE_MAP",
    "MEASURE_CURRENT_RANGE_MAP",
    "MEASURE_VOLTAGE_RANGE_MAP",
    "MEASURE_EVENT_DATA_MAP",
    "WARNING_LEVEL_MAP",
]
