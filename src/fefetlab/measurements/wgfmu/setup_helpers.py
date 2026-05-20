"""Helpers for resilient WGFMU notebook setup.

Three small utilities that make notebook 21/23/24/25 robust against the
inevitable surprises every new test machine throws at us:

* :func:`ensure_wgfmu_dll_path` — set ``WGFMU_DLL_PATH`` to the first
  ``wgfmu.dll`` that actually exists on this box (System32 first, then
  common Keysight install paths).

* :func:`autodetect_visa_addr` — given a substring like ``B1500A`` or
  ``Agilent``, scan all VISA resources, ``*IDN?`` each one until we find
  the instrument we want, and return its address.  Saves yhzang from
  hard-coding ``GPIB0`` vs ``GPIB1``.

* :func:`autodetect_wgfmu_chan` — call ``backend.get_channel_ids()`` and
  return the first channel id, or check that a given chan_id is present.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional


_DLL_SEARCH = [
    r"C:\Windows\System32\wgfmu.dll",
    r"C:\Program Files\Keysight\B1530A\bin\wgfmu.dll",
    r"C:\Program Files\Keysight\B1500A\WGFMU\bin\wgfmu.dll",
    r"C:\Program Files (x86)\Keysight\B1500A\WGFMU\bin\wgfmu.dll",
    r"C:\Program Files\Agilent\B1500A\WGFMU\bin\wgfmu.dll",
    r"C:\Program Files (x86)\Agilent\B1500\EasyEXPERT\Utilities\WGFMU\bin\wgfmu.dll",
]


def ensure_wgfmu_dll_path() -> str:
    """Find a working wgfmu.dll path and export it via WGFMU_DLL_PATH.

    Returns the chosen path. Raises ``FileNotFoundError`` if none works.
    """
    env = os.environ.get("WGFMU_DLL_PATH")
    if env and Path(env).is_file():
        return env
    for cand in _DLL_SEARCH:
        if Path(cand).is_file():
            os.environ["WGFMU_DLL_PATH"] = cand
            return cand
    raise FileNotFoundError(
        "wgfmu.dll not found. Install Keysight B1530A Instrument Library "
        "(places dll in C:\\Windows\\System32). Tried:\n  "
        + "\n  ".join(_DLL_SEARCH)
    )


def autodetect_visa_addr(
    needle: str = "B1500",
    *,
    candidates: Optional[Iterable[str]] = None,
    timeout_ms: int = 5000,
) -> str:
    """Find the VISA resource whose ``*IDN?`` contains ``needle``.

    Tries ``candidates`` (or all GPIB resources from ``list_resources()``),
    sending a short ``*IDN?`` to each with both common termination styles.
    Returns the first match. Raises ``RuntimeError`` if none respond.
    """
    import pyvisa  # local import — pyvisa is heavy

    rm = pyvisa.ResourceManager()
    try:
        if candidates is None:
            candidates = [r for r in rm.list_resources() if r.startswith("GPIB")]
        for addr in candidates:
            for write_term, read_term in (("\n", None), ("\r\n", "\r\n")):
                try:
                    inst = rm.open_resource(addr)
                    inst.timeout = timeout_ms
                    inst.write_termination = write_term
                    inst.read_termination = read_term
                    idn = inst.query("*IDN?").strip()
                    inst.close()
                    if needle.lower() in idn.lower():
                        return addr
                except Exception:
                    try:
                        inst.close()  # type: ignore[possibly-undefined]
                    except Exception:
                        pass
                    continue
        raise RuntimeError(
            f"No VISA resource matched {needle!r}. "
            f"Tried: {list(candidates)}"
        )
    finally:
        rm.close()


def autodetect_wgfmu_chan(
    backend,
    *,
    prefer: Optional[int] = None,
    require_rsu: bool = True,
) -> int:
    """Return a usable WGFMU channel id.

    If ``prefer`` is given and is in the channel list, return it; otherwise
    return the first detected channel.  Caller still has to verify the
    channel has an RSU connected (B1500 will report
    ``RSU is not connected; CHANNELxxx`` on setOperationMode if not).
    """
    ids = backend.get_channel_ids()
    if not ids:
        raise RuntimeError("WGFMU reported zero channels; check that the module is installed")
    if prefer is not None:
        if prefer in ids:
            return prefer
        raise RuntimeError(
            f"prefer={prefer} not in detected channels {ids}. "
            "Pick one of the detected ids."
        )
    return ids[0]


__all__ = [
    "ensure_wgfmu_dll_path",
    "autodetect_visa_addr",
    "autodetect_wgfmu_chan",
]
