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


def test_preview_done_failure_sets_status(qapp):
    from gui.app import MainWindow

    win = MainWindow()
    win.run_control.btn_preview.setEnabled(False)         # 模拟生成中
    win._on_preview_done({"ok": False, "error": "TESTFAIL"})
    assert "失败" in win.run_control.status.text()
    assert win.run_control.btn_preview.isEnabled()        # 完成后按钮恢复


def test_preview_worker_emits_result(qapp):
    from gui.app import _PreviewWorker

    got: list = []
    w = _PreviewWorker("E6S", {})
    w.done.connect(got.append)
    w.run()                                               # 同步跑(不 start),验证 emit
    assert got and got[0]["ok"]


def test_live_precondition_wiring_only(qapp):
    from gui.run_control_panel import RunControlPanel

    rc = RunControlPanel()
    assert not hasattr(rc, "ed_confirm")                  # 手输 stage 码的框已移除
    rc.rb_live.setChecked(True)
    assert rc.live_preconditions_ok() is False            # 没勾接线 → 不就绪
    rc.chk_wiring.setChecked(True)
    assert rc.live_preconditions_ok() is True             # 勾了接线就行,不用手输 stage


def test_tree_leaf_is_title_only(qapp):
    from PySide6.QtCore import Qt

    from fefetlab.engine import REGISTRY
    from gui.protocol_panel import ProtocolPanel

    p = ProtocolPanel()
    leaf = {}
    for i in range(p.tree.topLevelItemCount()):
        grp = p.tree.topLevelItem(i)
        for j in range(grp.childCount()):
            ch = grp.child(j)
            leaf[ch.data(0, Qt.ItemDataRole.UserRole)] = ch.text(0)
    assert leaf.get("E6M") == REGISTRY["E6M"].title       # 只显示形象名
    assert "E6M" not in leaf.get("E6M", "")               # 代号不在显示文本里
