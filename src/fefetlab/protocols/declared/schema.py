"""声明式协议 schema(DSL v1)· 纯数据,零仪器导入,可被任何调用方安全导入。

一个协议 = 一串 step(reset/pulse/delay/read)+ 可选一条 scan_axis + 双极性 states + rep。
约束(由 registry_glue 加载期校验):read 必须是 steps 的最后一个;scan_axis.step_index 合法。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ResetStep:
    t: float = 1e-3                 # 栅=0、漏=0 复位(秒)
    kind: Literal["reset"] = "reset"


@dataclass(frozen=True)
class PulseStep:
    v: float                        # 终点电压(含符号=极性)
    width: float                    # 平顶宽度(秒);升降沿固定 T_RF
    sign_by_state: bool = False     # True:幅值按 state 取号(ERS→+|v|, PGM→-|v|)
    kind: Literal["pulse"] = "pulse"


@dataclass(frozen=True)
class DelayStep:
    t: float                        # 栅=0、漏=0 弛豫(秒);可为 0
    kind: Literal["delay"] = "delay"


@dataclass(frozen=True)
class ReadStep:
    vg_list: tuple[float, ...]      # 在每个 Vg 点贴标准读窗
    vd: float                       # 读相漏极恒压
    n_pts: int = 5                  # 每窗采样点数(默认 N_PTS)
    kind: Literal["read"] = "read"


Step = ResetStep | PulseStep | DelayStep | ReadStep


@dataclass(frozen=True)
class ScanAxis:
    step_index: int                 # 改哪个 step
    param: Literal["v", "width", "t", "vd"]  # 改该 step 的哪个字段
    values: tuple[float, ...]
    label: str = "scan"             # CSV 列名 + GUI 旋钮名(如 "delay_s")


@dataclass(frozen=True)
class StopGate:
    ig_stop_uA: float = 0.0         # 0=不设门;>0 时 |Ig|>阈值 报停门


@dataclass(frozen=True)
class DeclaredProtocol:
    id: str                         # 协议码(REGISTRY key)
    title: str                      # GUI 叶子名(形象名)
    physics: str = "custom"
    description: str = ""
    group: str = "自定义协议"
    steps: tuple[Step, ...] = ()
    states: tuple[str, ...] = ("ERS", "PGM")   # 双极性;()=单态
    reps: int = 1
    scan_axis: ScanAxis | None = None
    stop_gate: StopGate | None = None
