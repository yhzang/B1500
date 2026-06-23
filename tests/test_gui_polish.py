"""打磨件测试:菜单栏 / 状态栏接线指示 / 安全指标(max|Ig|)/ on_shot 喂入 / 关闭持久化。"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def test_mainwindow_has_menus(qapp):
    from gui.app import MainWindow

    win = MainWindow()
    texts = [a.text() for a in win.menuBar().actions()]
    for name in ("文件", "视图", "设备", "帮助"):
        assert any(name in t for t in texts), f"缺菜单 {name}: {texts}"


def test_status_bar_shows_wiring(qapp):
    from gui.app import MainWindow

    win = MainWindow()
    t = win._wiring_label.text()
    assert "Gate=202" in t and "Drain=201" in t


def test_run_control_safety_metric(qapp):
    from gui.run_control_panel import RunControlPanel

    rc = RunControlPanel()
    rc.update_safety(5.0)
    assert "5" in rc._safety.text() and "B80000" not in rc._safety.styleSheet()
    rc.update_safety(2.0)            # 更小 → 不覆盖最大值
    assert "5" in rc._safety.text()
    rc.update_safety(25.0)           # >20 → 红粗
    assert "25" in rc._safety.text() and "B80000" in rc._safety.styleSheet()
    rc.reset_safety()
    assert "--" in rc._safety.text()


def test_on_shot_feeds_safety(qapp):
    from gui.app import MainWindow

    win = MainWindow()
    win.run_control.reset_safety()
    win._on_shot("E1", 0, [
        {"state_target": "ERS", "Ig_mean_A": 3.0e-5},    # 30 µA
        {"state_target": "PGM", "Ig_mean_A": -1.0e-5},   # 10 µA(abs)
    ])
    assert "30" in win.run_control._safety.text()


def test_live_toggle_updates_preflight(qapp):
    from gui.run_control_panel import RunControlPanel

    rc = RunControlPanel()
    assert "dry 模拟" in rc._pf_errx.text()
    rc.rb_live.setChecked(True)
    assert "live" in rc._pf_errx.text()


def test_close_event_persists_layout(qapp):
    from gui.app import MainWindow

    win = MainWindow()
    win.close()  # closeEvent 写 QSettings,不应抛
