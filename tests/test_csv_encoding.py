"""增量3:CSV 写入一律 UTF-8 无 BOM。

全局规约(CLAUDE.md):写供他人/他 AI 读的文件一律 UTF-8 无 BOM。BOM(utf-8-sig)会破坏
下游解析(项目4 回流)。此守门确保 CSV 写入器不再用 utf-8-sig。
"""
from __future__ import annotations

from pathlib import Path

import fefetlab.measurements.dc.export as dce
import fefetlab.measurements.wgfmu.export as we
import fefetlab.measurements.wgfmu.iv_sweep as ivs
import fefetlab.measurements.wgfmu.wakeup as wk


def test_no_bom_utf8sig_in_csv_writers():
    for mod in (dce, we, ivs, wk):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "utf-8-sig" not in src, f"{mod.__name__} 仍以 utf-8-sig(BOM)写 CSV"
