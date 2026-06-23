#!/usr/bin/env python
"""[薄壳] 单写 WGFMU 协议(E1S/E6S/E6M)CLI 入口。

2026-06-23 搬家:全部协议逻辑已搬到 ``fefetlab.protocols.wgfmu_single_shot``,以便升格进
engine REGISTRY 让 GUI 可驱动。本文件只保留命令行入口,CLI 行为(stdout/CSV/manifest)与
搬家前**逐字节一致**(golden 守护)。直跑用法不变:

    python scripts/wgfmu_single_shot_disturb.py --stage E1S --device-id <X> --geometry L10W10

负值列表参数仍用 '=',例如  --read-vg=-1.0,-0.7 。
"""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fefetlab.protocols.wgfmu_single_shot import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
