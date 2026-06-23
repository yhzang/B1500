"""DSL v1:声明式自定义协议经引擎门 dry 跑通 + 注册隔离(全 dry,本机可跑)。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from fefetlab.engine import ProtocolEngine, REGISTRY, RecordingCallbacks
from fefetlab.measurements.wgfmu.audit_backend import AuditBackend
from fefetlab.protocols.wgfmu_fefet import DRAIN_CH, GATE_CH


def _dry_backend() -> AuditBackend:
    b = AuditBackend(gate_ch=GATE_CH, drain_ch=DRAIN_CH, channels=[201, 202, 301, 302])
    b.open_session("DUMMY::WGFMU")
    b._fefet_visa_addr = "DUMMY::WGFMU"
    b._fefet_wgfmu_initialized = False
    return b


def test_declared_demo_ret_dry_through_engine(tmp_path):
    """family=CUSTOM 段:引擎旁路 configure_channel_map,声明式编译成向量 dry 跑通产 CSV。"""
    params = {
        "device_id": "DECL", "geometry": "L40W10", "serial": "",
        "reps": 1, "n_pts": 5, "delay_s": "0,1e-3,1e-2",   # GUI 改扫描值 → 以 view 为准
        "live": False, "out_root": str(tmp_path),
    }
    cb = RecordingCallbacks()
    summary = ProtocolEngine().run("DEMO_RET", params, backend=_dry_backend(), callbacks=cb)
    assert summary.report_code == "DEMO_RET_DONE"
    out = Path(summary.out_csv)
    assert out.exists() and out.name == "data.csv"
    assert (out.parent / "manifest.yaml").exists()
    df = pd.read_csv(out)
    assert {"Id_mean_A", "state_target", "delay_s", "Vg_read_V"} <= set(df.columns)
    # 2 states × 3 delays × 1 rep × 5 Vg = 30 行
    assert len(df) == 2 * 3 * 1 * 5
    shots = [e for e in cb.events if e[0] == "shot"]
    assert len(shots) == 2 * 3 * 1  # 每炮一次 on_shot


def test_declared_registered_and_isolated():
    assert "DEMO_RET" in REGISTRY
    spec = REGISTRY["DEMO_RET"]
    assert spec.family == "CUSTOM"          # 独立 family
    assert spec.csv_schema == "fefet_fixedcols"  # 复用现成读相口径(实时图/结果图都生效)
    assert spec.group == "自定义协议"
    assert callable(spec.runner)
    assert spec.params  # 有表单料(reps/n_pts/通道/扫描轴/停门)
