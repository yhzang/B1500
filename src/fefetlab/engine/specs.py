"""引擎核心 · 唯一权威参数/协议规格 (纯数据)。

设计文档 §3.1。这是 GUI 表单生成、CLI argparse、参数校验、manifest 写入
四件事的**唯一权威来源**——消灭"参数散在 模块全局 / argparse / yaml / dataclass
四处"的现状。本模块刻意保持纯数据:零仪器导入、零 Qt、零业务逻辑,可被任何
调用方(引擎 / GUI / CLI / 测试)安全导入。

字段对照(旧来源 → ParamSpec):
  * argparse 的 type/default/help        → kind/default/help
  * 模块全局(V_ERS/T_WRITE/VG_READS…)   → default(直接写论文标称值)
  * 九个 --*-ig-stop-uA                  → 每协议一个 ParamSpec + ProtocolSpec.stop_gate
  * _resolve_* 的 "None 回退全局" 裁决     → default 写死,runner 内 _resolve_* 原样保留

ProtocolSpec 是旧 orchestration.core.StageSpec(name/output_label/description/runner)
的**超集**;迁移期由 as_stage_spec() 提供向后兼容。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ParamKind(Enum):
    """参数值类型。FLOAT_LIST/INT_LIST 对应 CLI 里的逗号分隔解析。"""

    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    FLOAT_LIST = "float_list"   # 对应 _parse_float_list_csv,如 e6d_delays
    INT_LIST = "int_list"       # 对应 _parse_int_list_csv,如 cycle_checkpoints
    CHOICE = "choice"


class Visibility(Enum):
    """三档可见性(取代草稿的 editable 布尔与 U/A/L 字符串)。

    判据:
      BASIC    改它不破安全不变量、且是实验自变量(器件相关:写电压/延迟/reps…)。
      ADVANCED 有合理默认、是方法学/复现旋钮(stop-gate 阈值/seed/量程…),藏在"高级"折叠。
      LOCKED   物理/接线/会话铁律,错值会烧器件/打错通道/会话死锁;GUI 只读或需二次确认+审计。
    """

    BASIC = "basic"
    ADVANCED = "advanced"
    LOCKED = "locked"


class Widget(Enum):
    """GUI 控件提示。GUI 据此选 Qt 控件;CLI 忽略。"""

    DOUBLE_SPINBOX = "double_spinbox"
    SPINBOX = "spinbox"
    CHECKBOX = "checkbox"
    CSV_LINE = "csv_line"        # 逗号分隔的浮点/整数列表
    COMBO = "combo"              # 配合 choices
    CHANNEL = "channel"          # 通道选择(接线档案)


@dataclass(frozen=True)
class ParamSpec:
    """单个参数的权威规格。name 同时是:引擎接收键 == argparse dest == manifest 键。"""

    name: str                       # 唯一权威键名(蛇形):"vd_read" / "e1_ig_stop_uA"
    label: str                      # 中文显示名:"读出 Vd"
    kind: ParamKind
    default: Any
    unit: str = ""                  # "V" / "s" / "µA";GUI 按 unit 做 SI 缩放(µs↔1e-6)
    visibility: Visibility = Visibility.BASIC
    minimum: float | None = None    # 统一用 minimum/maximum(非 min/max)
    maximum: float | None = None
    choices: tuple[Any, ...] | None = None
    widget: Widget = Widget.DOUBLE_SPINBOX
    cli_flag: str | None = None     # "--vd-read";None = 不暴露给 CLI
    device_overridable: bool = False  # pFeFET/nFeFET 是否分别给默认(见 ProtocolSpec.family_defaults)
    depends_on: str | None = None   # 仅当另一参数为真/非空时才生效(如 prebias_s 依赖 prebias_v)
    help: str = ""

    @property
    def editable(self) -> bool:
        """兼容读法:LOCKED 即不可编辑。"""
        return self.visibility is not Visibility.LOCKED


@dataclass(frozen=True)
class PlotHint:
    """结果图谱建议,供 GUI 跑完自动出图 / 实时绘图选轴。"""

    schema: str        # "fefet_fixedcols" | "iv_sweep" | "dc" | "wakeup_cycles"
    kind: str          # "mw_vs_delay" | "mw_vs_cycle" | "id_vg" | "ref_vs_disturb" ...
    x: str             # CSV 列名,如 "delay_s"
    y: str             # CSV 列名,如 "Id_mean_A"
    group_by: str = "" # 如 "state_target"(ERS/PGM 分色)


@dataclass(frozen=True)
class ProtocolSpec:
    """一个协议(=旧"阶段")的权威规格。旧 StageSpec 的超集。"""

    id: str                         # 阶段码 "E1"/"E6D"/"DC_IDVG"/"WAKEUP"/"CUSTOM"
    title: str                      # "RAWD 写后延迟读"
    family: str                     # "WGFMU" | "SMU" | "WGFMU_WAKEUP"
    physics: str                    # "retention" | "read-disturb" | "imprint" | ...
    description: str
    params: tuple[ParamSpec, ...]
    stop_gate: Any = None           # orchestration.core.StopGatePolicy | None(避免在纯数据层导入)
    csv_schema: str = "fefet_fixedcols"  # "fefet_fixedcols"(FIELDNAMES)/"dc"/"iv_sweep"/"wakeup_cycles"
    group: str = ""                 # GUI 协议树分组名(按"测什么":自检/保持/动力学/扰动…);空=回退 family
    requires: tuple[str, ...] = ()  # 门禁链:期望已完成的上游 report_code
    family_defaults: dict = field(default_factory=dict)  # {"pFeFET":{...},"nFeFET":{...}} 仅差异项
    plot_hints: tuple[PlotHint, ...] = ()
    note: str = ""                  # 如 "pFeFET 建议先唤醒"
    output_label: str = ""          # = 旧 StageSpec.output_label;空则回退到 id
    runner: Callable[..., Any] = None  # 适配后的 run_stage_*(backend, view, *, callbacks=None)

    def as_stage_spec(self):
        """迁移期向后兼容:产出旧 orchestration.core.StageSpec 四元组形态。

        仍引用 StageSpec 的旧代码(如 _summarize 取 spec.output_label)可继续工作,
        逐步退役后删除本方法。
        """
        from ..orchestration.core import StageSpec  # 延迟导入,保持本模块零依赖

        return StageSpec(
            name=self.id,
            output_label=self.output_label or self.id,
            description=self.description,
            runner=self.runner,
        )
