"""ISPP 闭环(项目5 杀手锏)守门:决策纯函数 + dry 端到端跑通。

闭环=data-dependent 逐炮编排(EasyEXPERT 开环模板表达不了的那一类)。这里:
  1) `_ispp_next` 纯函数逐条验收(无硬件):达标/饱和/触顶/继续。
  2) 经引擎门 dry 跑通:擦除 + ≥1 程序炮、每炮发 on_shot、确定性终止、产出 summary。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from fefetlab.engine import ProtocolEngine, REGISTRY, RecordingCallbacks
from fefetlab.measurements.wgfmu.audit_backend import AuditBackend
from fefetlab.protocols.wgfmu_fefet import DRAIN_CH, GATE_CH, _ispp_next, parse_args


# ── 1) 闭环决策纯函数(无硬件,逐条) ──────────────────────────────────────────
def test_ispp_next_target_reached():
    reason, amp = _ispp_next(2e-7, None, 2.0, target_id=1e-7, tol=1e-9, vg_step=0.25, vg_max=5.0)
    assert reason == "TARGET_REACHED" and amp == 2.0


def test_ispp_next_saturated():
    reason, _ = _ispp_next(5e-8, 5e-8, 2.0, target_id=1e-7, tol=1e-9, vg_step=0.25, vg_max=5.0)
    assert reason == "SATURATED"


def test_ispp_next_vg_max():
    reason, _ = _ispp_next(0.0, 1.0, 5.0, target_id=1e-7, tol=1e-9, vg_step=0.25, vg_max=5.0)
    assert reason == "VG_MAX"


def test_ispp_next_continue_increments():
    reason, amp = _ispp_next(0.0, 1.0, 2.0, target_id=1e-7, tol=1e-9, vg_step=0.25, vg_max=5.0)
    assert reason is None and abs(amp - 2.25) < 1e-12


def test_ispp_registered():
    assert "ISPP" in REGISTRY
    assert callable(REGISTRY["ISPP"].runner)
    assert REGISTRY["ISPP"].params  # 非空(GUI 表单料)


# ── 2) dry 端到端(引擎门) ────────────────────────────────────────────────────
def _dry_backend() -> AuditBackend:
    b = AuditBackend(gate_ch=GATE_CH, drain_ch=DRAIN_CH, channels=[201, 202, 301, 302])
    b.open_session("DUMMY::WGFMU")
    b._fefet_visa_addr = "DUMMY::WGFMU"
    b._fefet_wgfmu_initialized = False
    return b


def _cleanup(out_csv: Path) -> None:
    for anc in Path(out_csv).parents:
        if anc.name == "GOLDEN_ISPP":
            shutil.rmtree(anc, ignore_errors=True)
            break


def test_ispp_runner_dry_closed_loop_completes():
    params = vars(parse_args([
        "--stage", "ISPP", "--device-id", "GOLDEN_ISPP", "--geometry", "L40W10",
        "--seed", "20260522", "--ispp-max-steps", "4",
    ]))
    cb = RecordingCallbacks()
    out_csv = None
    try:
        summary = ProtocolEngine().run("ISPP", params, backend=_dry_backend(), callbacks=cb)
        out_csv = Path(summary.out_csv)
        assert summary.report_code == "ISPP_CLOSED_LOOP_DONE"
        shots = [e for e in cb.events if e[0] == "shot"]
        assert len(shots) >= 2, f"应至少 擦除1 + 程序≥1 炮,实际 {len(shots)}"
        assert shots[0][1] == "ISPP"
        # 程序炮数受 max_steps 上限约束(保证终止)
        program_shots = len(shots) - 1
        assert 1 <= program_shots <= 4
    finally:
        if out_csv is not None:
            _cleanup(out_csv)
