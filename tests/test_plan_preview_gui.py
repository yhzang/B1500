"""Plan 时序预览的 GUI 接线:预演按钮 / 改名 / 预览对话框可构建。"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def test_run_control_has_preview_and_renamed(qapp):
    from gui.run_control_panel import RunControlPanel

    rc = RunControlPanel()
    assert hasattr(rc, "btn_preview")
    assert "预演" in rc.rb_dry.text() or "Plan" in rc.rb_dry.text()


def test_timing_preview_dialog_builds(qapp):
    pytest.importorskip("pyqtgraph")
    from gui.plan_preview import build_timing_preview
    from gui.timing_preview_dialog import TimingPreviewDialog

    r = build_timing_preview("E6S")
    assert r["ok"], r.get("error")
    dlg = TimingPreviewDialog(r)          # 只构建,不 exec(modal 会阻塞)
    assert dlg.windowTitle()


def test_mainwindow_preview_no_protocol_guard(qapp):
    from gui.app import MainWindow

    win = MainWindow()
    # 新窗未选协议:_on_preview 走早退守卫(不弹 modal,不 build),提示选协议
    win._on_preview()
    assert "协议" in win.run_control.status.text()


def test_mainwindow_preview_failure_sets_status(qapp, monkeypatch):
    import gui.plan_preview as pp
    from gui.app import MainWindow

    win = MainWindow()
    win.protocol_panel.select_protocol("E6S")     # 选上协议,越过早退守卫
    # build 失败时设错误状态、不弹 modal(exec 会阻塞测试)
    monkeypatch.setattr(pp, "build_timing_preview", lambda *a, **k: {"ok": False, "error": "TESTFAIL"})
    win._on_preview()
    assert "失败" in win.run_control.status.text()
