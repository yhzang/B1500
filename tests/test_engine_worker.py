"""EngineWorker dry 集成测试:直接同步调 worker.run(),验证 GUI↔引擎整条路径。

不起 QThread/事件循环——sender 与 receiver 同线程时 Qt 用 DirectConnection,
信号同步触发到收集器。验证:WGFMU 段与 DC 段(family=SMU,走 make_backend_for→MockB1500)
都能跑完、emit stageDone、不 emit errorOccurred。这是壳里唯一真正"按下运行"的代码路径,
此前无测试覆盖(test_gui_smoke 只验装配,不跑 worker)。
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def _collect(worker):
    ev = {"done": [], "err": [], "plan": [], "stop": []}
    worker.stageDone.connect(lambda s, d: ev["done"].append((s, d)))
    worker.errorOccurred.connect(lambda e, r: ev["err"].append((e, r)))
    worker.planReady.connect(lambda p: ev["plan"].append(p))
    worker.stopGate.connect(lambda c, m, r: ev["stop"].append((c, m, r)))
    return ev


def test_worker_runs_wgfmu_dry(qapp, tmp_path):
    from gui.engine_worker import EngineWorker
    from gui.models import RunRequest

    req = RunRequest(stage="E1",
                     params={"device_id": "WTEST", "geometry": "L40W10"},
                     live=False, confirm="", out_root=str(tmp_path))
    w = EngineWorker(req)
    ev = _collect(w)
    w.run()
    assert not ev["err"], f"WGFMU worker 报错:{ev['err']}"
    assert ev["done"], "未收到 stageDone"
    assert ev["plan"], "未收到编程波形 planReady"


def test_worker_runs_dc_dry(qapp, tmp_path):
    """DC 段(family=SMU)走 make_backend_for→MockB1500,而非 AuditBackend。"""
    from gui.engine_worker import EngineWorker
    from gui.models import RunRequest

    req = RunRequest(
        stage="DC_IDVG",
        params={"device_id": "DCDEV", "geometry": "L40W10", "serial": "",
                "gate_ch": 4, "drain_ch": 5, "smu_s_ch": 6,
                "dc_vg_points": "0,-0.5,-1.0", "dc_vd_fixed": -0.1, "dc_vs_fixed": 0.0},
        live=False, confirm="", out_root=str(tmp_path))
    w = EngineWorker(req)
    ev = _collect(w)
    w.run()
    assert not ev["err"], f"DC worker 报错:{ev['err']}"
    assert ev["done"], "DC 未收到 stageDone"
