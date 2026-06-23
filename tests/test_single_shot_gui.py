"""单写族 E1S/E6S/E6M 接进 GUI:在 REGISTRY、在协议树、worker 能 dry 跑通。

这是"下次去实验直接点就能跑"的地基——项目4 真实实验全用单写协议(脆弱 L10 每 shot 只写一次),
此前只能命令行,现已升格进 engine REGISTRY 让 GUI 可驱动。
"""
from __future__ import annotations

import pytest


def _params_from_spec(sid):
    from fefetlab.engine import REGISTRY
    return {p.name: p.default for p in REGISTRY[sid].params}


def test_single_shot_registered():
    from fefetlab.engine import REGISTRY
    for sid in ("E1S", "E6S", "E6M"):
        assert sid in REGISTRY, f"{sid} 不在 REGISTRY"
        spec = REGISTRY[sid]
        assert spec.family == "WGFMU" and spec.group and spec.params
        assert callable(spec.runner)
    # 单写关键 flag 暴露为可调参数
    e1s = {p.name for p in REGISTRY["E1S"].params}
    assert {"read_vg", "delays", "write_state", "reps", "rich_read"} <= e1s
    e6m = {p.name for p in REGISTRY["E6M"].params}
    assert {"checkpoints", "disturb_amp", "interval_s", "e6m_state"} <= e6m


def test_single_shot_in_protocol_tree(qapp):
    from gui.protocol_panel import ProtocolPanel

    panel = ProtocolPanel()
    for sid in ("E1S", "E6S", "E6M"):
        assert panel.select_protocol(sid), f"{sid} 不在协议树"
    panel.select_protocol("E1S")
    out = panel.collect_params()
    assert "read_vg" in out and "delays" in out and "write_state" in out


def _run_worker(stage, tmp_path):
    pytest.importorskip("PySide6")
    from gui.engine_worker import EngineWorker
    from gui.models import RunRequest

    params = _params_from_spec(stage)
    params.update(device_id=f"SS_{stage}", geometry="L10W10")
    req = RunRequest(stage=stage, params=params, live=False, confirm="", out_root=str(tmp_path))
    w = EngineWorker(req)
    ev = {"done": [], "err": []}
    w.stageDone.connect(lambda s, d: ev["done"].append((s, d)))
    w.errorOccurred.connect(lambda e, r: ev["err"].append((e, r)))
    w.run()
    return ev


def test_worker_runs_e1s_dry(qapp, tmp_path):
    ev = _run_worker("E1S", tmp_path)
    assert not ev["err"], f"E1S worker 报错:{ev['err']}"
    assert ev["done"], "E1S 未收到 stageDone"


def test_worker_runs_e6s_dry(qapp, tmp_path):
    ev = _run_worker("E6S", tmp_path)
    assert not ev["err"], f"E6S worker 报错:{ev['err']}"
    assert ev["done"], "E6S 未收到 stageDone"


def test_worker_runs_e6m_dry(qapp, tmp_path):
    ev = _run_worker("E6M", tmp_path)
    assert not ev["err"], f"E6M worker 报错:{ev['err']}"
    assert ev["done"], "E6M 未收到 stageDone"
