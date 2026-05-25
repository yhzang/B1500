"""Minimal B1500 connection/preflight check.

This script is intentionally WGFMU-safe for yhzang's B1500A: it does not send
``*CLS`` or ``*RST``.  Use ``inst.clear()`` + ``ERRX?`` drain through the shared
helper, because this machine can enqueue ``+100,Undefined GPIB command`` on
``*CLS`` and then make ``WGFMU_openSession`` fail with status=-6.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow `python src/scripts/connect_test.py` from a fresh clone without install.
SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pyvisa

from fefetlab.measurements.wgfmu.setup_helpers import (
    autodetect_visa_addr,
    clear_b1500_status_for_wgfmu_open,
)


def main() -> None:
    rm = pyvisa.ResourceManager()
    try:
        resources = rm.list_resources()
        print("Resources:", resources)
    finally:
        rm.close()

    visa_addr = os.environ.get("B1500_VISA_ADDR")
    if not visa_addr:
        visa_addr = autodetect_visa_addr("B1500")
    print("VISA_ADDR:", visa_addr)

    idn = clear_b1500_status_for_wgfmu_open(visa_addr)
    print("B1500 preflight ERRX drain OK:", idn)
    print("Done.")


if __name__ == "__main__":
    main()
