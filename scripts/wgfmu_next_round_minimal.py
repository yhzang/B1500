#!/usr/bin/env python
"""[薄壳] WGFMU stop-gated 协议 CLI 入口。

M1 搬家(2026-06-10):全部协议逻辑已搬到 `fefetlab.protocols.wgfmu_fefet`。
本文件只保留命令行入口,CLI 行为(stdout / CSV / manifest)与搬家前**逐字节一致**,
由 `tests/test_cli_dry_golden.py` 金标准护栏守护。

为兼容"未 `pip install -e .` 直接 `python scripts/wgfmu_next_round_minimal.py`"
的用法,运行前把 `src/` 注入 sys.path 再导入包。已装包时该插入无害。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fefetlab.protocols.wgfmu_fefet import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
