"""器件软判定接进 GUI:阈值可改 + 判定显示 + stage_done 出横幅并记进 run_log。"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def test_run_control_health_thresholds_and_display(qapp):
    from gui.run_control_panel import RunControlPanel

    rc = RunControlPanel()
    th = rc.health_thresholds()
    assert th["conduction_uA"] == 5.0 and th["collapse_k"] == 3.0   # 默认
    rc._cond_uA.setValue(2.0)                                        # 可改
    assert rc.health_thresholds()["conduction_uA"] == 2.0
    rc.set_health("疑似窗塌(…)", status="collapse")
    assert "窗塌" in rc._health.text() and "B80000" in rc._health.styleSheet()
    rc.reset_safety()
    assert "—" in rc._health.text() and rc._health.styleSheet() == ""


def test_stage_done_health_banner_and_recorded(qapp, tmp_path):
    import pandas as pd

    from gui.app import MainWindow

    win = MainWindow()
    csv = tmp_path / "x.csv"
    # 主读点 Id 没过噪声(1e-8 < 3×1e-8)、Ig 健康 → 应判窗塌
    pd.DataFrame({"Vg_read_V": [-1.0], "Id_mean_A": [1e-8],
                  "Id_std_A": [1e-8], "Ig_mean_A": [1e-9]}).to_csv(csv, index=False)

    class _S:
        report_code = "E6M_DONE_DRY"
        out_csv = str(csv)
        max_abs_ig_a = 1e-9

    win._last_stage = "E6M"
    win._last_live = False
    win._on_stage_done(_S(), str(tmp_path))

    assert "窗塌" in win.run_control._health.text()                  # 横幅着色显示
    log = (tmp_path / "run_log.txt").read_text(encoding="utf-8")     # 记录
    assert "HEALTH_COLLAPSE" in log
