"""命名预设:文件 I/O round-trip + ParamForm 回填 + MainWindow 存/取整合。"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def test_presets_file_roundtrip(tmp_path):
    from gui import presets

    assert presets.list_presets(tmp_path) == []
    data = {"stage": "E1", "params": {"vd_read": 0.1}, "identity": {"device_id": "D1"}}
    p = presets.save_preset(tmp_path, "我的预设A", data)
    assert p.exists()
    assert not p.read_bytes().startswith(b"\xef\xbb\xbf")        # UTF-8 无 BOM
    assert "我的预设A" in presets.list_presets(tmp_path)
    loaded = presets.load_preset(tmp_path, "我的预设A")
    assert loaded["stage"] == "E1" and loaded["params"]["vd_read"] == 0.1
    assert presets.delete_preset(tmp_path, "我的预设A") is True
    assert presets.list_presets(tmp_path) == []


def test_param_form_apply_values(qapp):
    from fefetlab.engine import REGISTRY

    from gui.param_form import ParamForm

    form = ParamForm()
    form.set_protocol(REGISTRY["E1"])
    form.apply_values({"vd_read": 0.12})
    assert abs(form.collect()["vd_read"] - 0.12) < 1e-9


def test_mainwindow_preset_save_load(qapp, tmp_path):
    from gui.app import MainWindow

    win = MainWindow()
    win._presets_root = tmp_path
    assert win.protocol_panel.select_protocol("E1")
    win.protocol_panel.param_form.apply_values({"vd_read": 0.07})
    assert win.save_preset_as("setA") is True

    # 换协议 + 改值,再加载预设应恢复 E1 + vd_read=0.07
    win.protocol_panel.select_protocol("S0")
    assert win.load_preset_named("setA") is True
    assert win.protocol_panel.current_protocol_id() == "E1"
    assert abs(win.protocol_panel.collect_params()["vd_read"] - 0.07) < 1e-9
