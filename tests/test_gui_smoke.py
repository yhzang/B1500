"""GUI 初版离屏冒烟测试(在测试机跑;无 PySide6 自动 skip)。

只做"构造不抛 + ParamForm 覆盖每个协议每个 ParamSpec",不起事件循环、不跑引擎、不碰硬件。
真正的端到端 dry 跑通由 test_engine_run / test_cli_dry_golden 守(引擎层),GUI 这里只验装配。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 让 `import gui`(顶层包,不随 fefetlab 安装)可被找到
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from fefetlab.engine import REGISTRY  # noqa: E402

from gui.param_form import ParamForm  # noqa: E402


_APP = None  # 模块全局持有:否则测试结束 QApplication/widget 被 GC、析构顺序错乱会段错误(pytest-qt 经典坑)


def _ensure_app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


def test_param_form_covers_every_protocol_param():
    _ensure_app()
    form = ParamForm()
    for _pid, spec in REGISTRY.items():
        form.set_protocol(spec)
        out = form.collect()
        for p in spec.params:
            assert p.name in out, f"{spec.id} 缺字段 {p.name}"


def test_mainwindow_constructs():
    _ensure_app()
    from gui.app import MainWindow

    win = MainWindow()
    assert win.protocol_panel is not None
    assert win.controller is not None


def test_plotpanel_realtime_append_accumulates():
    """逐炮 on_shot 增量图:append_shot_rows 累积进缓冲,_flush_live 后每个 state 一条曲线。"""
    pytest.importorskip("pyqtgraph")
    _ensure_app()
    from gui.plot_panel import PlotPanel

    pp = PlotPanel()
    pp.begin_live_plot("fefet_fixedcols", live=False)
    assert pp._live_active is True
    pp.append_shot_rows("E1", 0, [
        {"state_target": "ERS", "delay_s": 1e-5, "Id_mean_A": 1.0e-6},
        {"state_target": "PGM", "delay_s": 1e-5, "Id_mean_A": -2.0e-6},
    ])
    pp.append_shot_rows("E1", 1, [
        {"state_target": "ERS", "delay_s": 1e-3, "Id_mean_A": 1.1e-6},
        {"state_target": "PGM", "delay_s": 1e-3, "Id_mean_A": -2.1e-6},
    ])
    pp._flush_live()
    assert set(pp._live_items) == {"ERS", "PGM"}
    for state in ("ERS", "PGM"):
        xs, ys = pp._live_items[state].getData()
        assert len(xs) == 2 and len(ys) == 2  # 两炮各一点

    # 非实时 schema:begin 不启用实时,append 被忽略,无曲线
    pp.begin_live_plot("dc", live=False)
    assert pp._live_active is False
    pp.append_shot_rows("DC", 0, [{"state_target": "ERS", "delay_s": 1, "Id_mean_A": 1e-6}])
    pp._flush_live()
    assert pp._live_items == {}


def test_plotpanel_realtime_skips_nan_and_missing():
    """缺 Id_mean_A / 非数值的行被跳过,不进缓冲。"""
    pytest.importorskip("pyqtgraph")
    _ensure_app()
    from gui.plot_panel import PlotPanel

    pp = PlotPanel()
    pp.begin_live_plot("fefet_fixedcols", live=False)
    pp.append_shot_rows("E1", 0, [
        {"state_target": "ERS", "delay_s": 1e-5, "Id_mean_A": ""},      # 空 → 跳过
        {"state_target": "ERS", "delay_s": 1e-5},                        # 缺列 → 跳过
        {"state_target": "ERS", "delay_s": 1e-5, "Id_mean_A": 5.0e-7},  # 有效
    ])
    pp._flush_live()
    xs, ys = pp._live_items["ERS"].getData()
    assert len(xs) == 1 and ys[0] == 5.0e-7
