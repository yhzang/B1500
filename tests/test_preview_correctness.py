"""时序预览正确性(锁定):已知输入→已知波形(手算)+ 真协议参数对照 + 折线自洽。

预览走与真跑同一个 engine.run;AuditBackend 记录的 add_vector/measure_event 即 live 时
RealWgfmuBackend 发给 WGFMU 的同一批调用。本测试证明"从这些向量抽出来画的"忠实。
"""
from __future__ import annotations

from fefetlab.protocols.declared.schema import (
    DelayStep,
    DeclaredProtocol,
    PulseStep,
    ReadStep,
    ResetStep,
)
from fefetlab.protocols.wgfmu_fefet import T_RF

from gui.plan_preview import build_timing_preview, preview_declared


def _ap(a, b, tol=2e-9):
    return abs(a - b) <= tol + 1e-6 * abs(b)


def test_preview_hand_recipe_exact():
    # reset 1ms → +4V/100µs 脉冲 → delay 2ms → read −1V:波形该长什么样是手算可知的
    decl = DeclaredProtocol(
        id="VERIFY", title="v",
        steps=(ResetStep(t=1e-3), PulseStep(v=4.0, width=100e-6), DelayStep(t=2e-3),
               ReadStep(vg_list=(-1.0,), vd=0.05, n_pts=5)),
        states=("ERS",))
    r = preview_declared(decl)
    assert r["ok"], r.get("note")
    assert any(_ap(p["v"], 4.0) and _ap(p["width"], 100e-6) for p in r["pulses"])   # 脉冲 +4V/100µs
    assert any(_ap(x["v"], -1.0) for x in r["reads"])                               # 读 Vg=−1V
    exp_read = 1e-3 + (T_RF + 100e-6 + T_RF) + 2e-3                                  # reset+脉冲(含沿)+delay
    assert r["read_events_s"] and exp_read <= r["read_events_s"][0] <= exp_read + 20e-6  # 读发生时刻


def test_preview_e6s_matches_params():
    r = build_timing_preview("E6S")
    assert r["ok"]
    pv = [p["v"] for p in r["pulses"]]
    rv = [x["v"] for x in r["reads"]]
    assert any(_ap(v, 5.0) for v in pv)      # ERS 写 +5V(write_v 默认 ±5)
    assert any(_ap(v, -2.5) for v in pv)     # 扰动 −2.5V(disturb_amp 反号)
    assert any(_ap(v, -1.0) for v in rv) and any(_ap(v, -0.7) for v in rv)  # 读 −1.0/−0.7


def test_preview_waveform_self_consistent():
    r = preview_declared(DeclaredProtocol(
        id="V2", title="v",
        steps=(ResetStep(t=1e-3), PulseStep(v=4.0, width=100e-6),
               ReadStep(vg_list=(-1.0,), vd=0.05)),
        states=("ERS",)))
    gp = r["gate_points"]
    assert all(gp[i][0] <= gp[i + 1][0] for i in range(len(gp) - 1))                # 时间单调
    assert _ap(gp[-1][0], r["summary"]["total_shot_duration_s"])                    # 折线终点 = 总时长
