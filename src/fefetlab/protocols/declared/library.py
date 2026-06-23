"""声明式协议库 · 工程师在这里加协议(只填数据,无需写 Python 逻辑)。

照 DEMO_RET 复制一份、改 steps/scan_axis/states 即可定义新协议;存盘后自动出现在 GUI
「自定义协议」分组,可 dry 跑、跑完出图。(后续可扩成 YAML 加载,本 v1 先用 dataclass 列表。)
"""
from __future__ import annotations

from .schema import DeclaredProtocol, DelayStep, PulseStep, ReadStep, ResetStep, ScanAxis, StopGate

# 示例:写后延迟读(声明式版,演示如何不写代码定义一个保持特性协议)
DEMO_RET = DeclaredProtocol(
    id="DEMO_RET",
    title="示例 · 写后延迟读(声明式)",
    physics="retention",
    description=("reset → 写脉冲(±2.5V/100µs,按 ERS/PGM 取号) → 延迟(扫 5 档) → "
                 "在 5 个 Vg 点读 Id。这是声明式协议示范:复制本条改 steps/scan_axis 即可加自己的。"),
    group="自定义协议",
    steps=(
        ResetStep(t=1e-3),
        PulseStep(v=2.5, width=100e-6, sign_by_state=True),
        DelayStep(t=0.0),                                              # 被 scan 改写
        ReadStep(vg_list=(0.0, -0.5, -1.0, -1.5, -2.0), vd=-0.1, n_pts=5),
    ),
    states=("ERS", "PGM"),
    reps=1,
    scan_axis=ScanAxis(step_index=2, param="t",
                       values=(0.0, 1e-3, 1e-2, 1e-1, 1.0), label="delay_s"),
    stop_gate=StopGate(ig_stop_uA=30.0),
)

DECLARED_PROTOCOLS = [DEMO_RET]
