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


def test_write_conduction_warn_decision(qapp):
    from gui.app import MainWindow

    win = MainWindow()
    win._warn_no_conduction = True                                   # 不依赖 QSettings 现状
    win.run_control._id_edits["device_id"].setText("DEVA")
    assert win._should_warn_no_conduction("E6M") is False            # 还没读过 → 不提示
    win._last_health_status = "low_id"
    win._last_health_device = "DEVA"
    assert win._should_warn_no_conduction("E6M") is True             # 写类 + 没导通 + 同器件
    assert win._should_warn_no_conduction("S1") is False            # 只读类不提示
    win._last_health_device = "DEVB"
    assert win._should_warn_no_conduction("E6M") is False            # 判定不是这颗 → 不吓人
    win._last_health_device = "DEVA"
    win._last_health_status = "ok"
    assert win._should_warn_no_conduction("E6M") is False            # 导通正常 → 不提示
    win._last_health_status = "no_data"
    assert win._should_warn_no_conduction("E6M") is False            # 没读到有效数据≠没导通,不弹


def test_write_warn_text_by_family(qapp):
    from gui.app import MainWindow

    win = MainWindow()
    assert "只写一次" in win._write_warn_text("E6M")                  # 单写族:白费一炮口吻
    assert "只写一次" not in win._write_warn_text("E1")               # 多写族:可重写,中性
    assert "只写一次" not in win._write_warn_text("CYCLE")


def test_warn_dismiss_persists_and_reenable(qapp):
    from PySide6.QtCore import QSettings

    from gui.app import _APPNAME, _ORG, MainWindow

    s = QSettings(_ORG, _APPNAME)
    orig = s.value("health/warn_no_conduction", True, type=bool)
    try:
        s.setValue("health/warn_no_conduction", True)
        win = MainWindow()
        win._last_health_status = "low_id"
        win._last_health_device = "DEVA"
        win.run_control._id_edits["device_id"].setText("DEVA")
        assert win._should_warn_no_conduction("E6M") is True

        win._set_warn_no_conduction(False)                           # 勾"不再提示"
        assert win._warn_no_conduction is False
        assert win._should_warn_no_conduction("E6M") is False        # 之后不再弹
        assert win.act_warn_cond.isChecked() is False                # 菜单同步
        assert s.value("health/warn_no_conduction", True, type=bool) is False  # 持久化

        win.act_warn_cond.setChecked(True)                           # 设备菜单可重新打开
        assert win._warn_no_conduction is True
        assert win._should_warn_no_conduction("E6M") is True
    finally:
        s.setValue("health/warn_no_conduction", orig)               # 还原,免污染
