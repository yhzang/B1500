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


def _widget_for(form, name):
    for p, w in form._fields:
        if p.name == name:
            return p, w
    raise KeyError(name)


def test_param_form_typed_widgets_and_si_scaling():
    """增量2:INT→QSpinBox、FLOAT→QDoubleSpinBox;时间单位 µs 做 SI 缩放,µA 不缩放。"""
    _ensure_app()
    from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox

    from gui.param_form import ParamForm

    form = ParamForm()
    form.set_protocol(REGISTRY["ISPP"])
    out = form.collect()

    # 时间:ispp_width_s 默认 100e-6 s,单位 µs → 控件显示工程量 100,collect 还原秒
    _p, w = _widget_for(form, "ispp_width_s")
    assert isinstance(w, QDoubleSpinBox)
    assert abs(w.value() - 100.0) < 1e-6
    assert abs(out["ispp_width_s"] - 100e-6) < 1e-12
    # 电流:ispp_target_id_uA 默认 0.1(本就以 µA 存)→ 不缩放,collect 原样 0.1
    _p2, w2 = _widget_for(form, "ispp_target_id_uA")
    assert isinstance(w2, QDoubleSpinBox)
    assert abs(out["ispp_target_id_uA"] - 0.1) < 1e-12
    # INT → QSpinBox
    _p3, w3 = _widget_for(form, "ispp_max_steps")
    assert isinstance(w3, QSpinBox)
    assert out["ispp_max_steps"] == 16


def test_param_form_none_default_stays_none():
    """默认 None 的数值(=用协议标称)留可空文本框,空 → collect 返 None。"""
    _ensure_app()
    from gui.param_form import ParamForm

    form = ParamForm()
    form.set_protocol(REGISTRY["E1"])
    out = form.collect()
    assert out.get("vd_read", "MISSING") is None


def test_param_form_locked_is_readonly():
    """LOCKED 接线参数(gate_ch)只读,collect 原样返默认。"""
    _ensure_app()
    from PySide6.QtWidgets import QLineEdit

    from gui.param_form import ParamForm

    form = ParamForm()
    form.set_protocol(REGISTRY["E1"])
    p, w = _widget_for(form, "gate_ch")
    assert isinstance(w, QLineEdit) and w.isReadOnly()
    assert form.collect()["gate_ch"] == p.default


def test_param_form_invalid_csv_flags_and_raises():
    """列表参数非法格式 → is_valid False + 红框 + collect 抛 ValueError;改回合法即恢复。"""
    import pytest as _pt

    _ensure_app()
    from gui.param_form import ParamForm

    form = ParamForm()
    form.set_protocol(REGISTRY["E6D"])
    _p, w = _widget_for(form, "e6d_delays")
    w.setText("1e-6, abc")
    assert form.is_valid() is False
    with _pt.raises(ValueError):
        form.collect()
    w.setText("1e-6, 1e-5")
    assert form.is_valid() is True


def test_param_form_choice_renders_combo():
    """CHOICE / 带 choices 的 COMBO → QComboBox(用合成 spec,不依赖 registry 是否已有 choices)。"""
    _ensure_app()
    from PySide6.QtWidgets import QComboBox

    from fefetlab.engine.specs import ParamKind, ParamSpec, ProtocolSpec, Widget

    from gui.param_form import ParamForm

    spec = ProtocolSpec(
        id="X", title="t", family="WGFMU", physics="p", description="d",
        params=(ParamSpec(name="mode", label="模式", kind=ParamKind.CHOICE, default="averaged",
                          choices=("averaged", "raw"), widget=Widget.COMBO),),
    )
    form = ParamForm()
    form.set_protocol(spec)
    _p, w = form._fields[0]
    assert isinstance(w, QComboBox)
    assert form.collect()["mode"] == "averaged"


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


def _fefet_df():
    import pandas as pd
    return pd.DataFrame({
        "state_target": ["ERS", "ERS", "PGM", "PGM"],
        "delay_s": [1e-5, 1e-3, 1e-5, 1e-3],
        "Id_mean_A": [1e-6, 1.1e-6, -2e-6, -2.1e-6],
        "Id_std_A": [1e-8, 1e-8, 1e-8, 1e-8],
        "Ig_mean_A": [1e-9, 1e-9, 1e-9, 1e-9],
    })


def test_fefet_plots_show_ig_adds_curves():
    """增量5:options show_ig=True 多画 Ig 曲线(安全量)。"""
    pytest.importorskip("pyqtgraph")
    _ensure_app()
    import pyqtgraph as pg

    from gui.adapters.fefet_plots import plot_fefet_fixedcols

    df = _fefet_df()
    w1 = pg.PlotWidget()
    plot_fefet_fixedcols(df, w1, live=False, options={"show_id": True, "show_ig": False})
    w2 = pg.PlotWidget()
    plot_fefet_fixedcols(df, w2, live=False, options={"show_id": True, "show_ig": True})
    assert len(w2.listDataItems()) > len(w1.listDataItems())


def test_fefet_plots_error_bars():
    """增量5:options error_bars=True 加 Id_std 误差棒。"""
    pytest.importorskip("pyqtgraph")
    _ensure_app()
    import pyqtgraph as pg

    from gui.adapters.fefet_plots import plot_fefet_fixedcols

    w = pg.PlotWidget()
    plot_fefet_fixedcols(_fefet_df(), w, live=False, options={"show_id": True, "error_bars": True})
    assert any(isinstance(it, pg.ErrorBarItem) for it in w.plotItem.items)


def test_plotpanel_viz_toggle_replots(tmp_path):
    """增量5:结果图缓存 df;勾 Ig 触发重画(不重读 CSV);log 轴开关不崩。"""
    pytest.importorskip("pyqtgraph")
    _ensure_app()
    from gui.plot_panel import PlotPanel

    csv = tmp_path / "r.csv"
    _fefet_df().to_csv(csv, index=False)
    pp = PlotPanel()
    pp.show_result(str(csv), "fefet_fixedcols", live=False)
    assert pp._last_result is not None
    n0 = len(pp._result.listDataItems())
    pp._cb_ig.setChecked(True)              # toggled → _replot_result
    assert len(pp._result.listDataItems()) > n0
    pp._cb_logx.setChecked(True)            # toggled → _apply_axes(不崩)
    pp._cb_cursor.setChecked(True)          # 游标开(addItem 不崩)
    pp._cb_cursor.setChecked(False)         # 游标关(removeItem 不崩)


def test_app_writes_run_log_no_bom(tmp_path):
    """增量3:跑完把日志缓冲写进 run 目录 run_log.txt(UTF-8 无 BOM)。"""
    _ensure_app()
    from gui.app import MainWindow

    win = MainWindow()
    win.log_panel.append("INFO", "RUN_START", "stage=E1 live=False")
    win.log_panel.append("STOP", "E1_STOP", "boom")

    class _S:
        report_code = "X_DONE"
        out_csv = None

    win._on_stage_done(_S(), str(tmp_path))
    p = tmp_path / "run_log.txt"
    assert p.exists()
    raw = p.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")  # 无 BOM
    text = p.read_text(encoding="utf-8")
    assert "RUN_START" in text and "E1_STOP" in text
