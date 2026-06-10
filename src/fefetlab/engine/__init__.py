"""fefetlab 引擎核心 (headless,零 Qt)。

设计文档 §3。把现状(1378 行 WGFMU CLI + DC API + orchestration 层)收口成一个
GUI 与 CLI 共用的协议引擎内核。本包刻意不依赖 Qt,可被 CLI / 测试直接调用。

M1 渐进落地中,当前已就位:
  * specs       —— 唯一权威 ParamSpec / ProtocolSpec / PlotHint(纯数据,§3.1)
  * param_view  —— ParamView,让 run_stage_* 脱离 argparse 零改动(§3.4)
  * callbacks   —— EngineCallbacks 事件契约 + Null/Recording 实现(§3.6)
  * registry    —— REGISTRY:11 段升格为 ProtocolSpec(§3.2)
  * engine      —— ProtocolEngine.run 唯一执行门(§3.3)

后续:ParamSpec 逐参数枚举(+B7 常量提升)、build_argparser、BackendManager、on_shot 接入。
"""
from .callbacks import EngineCallbacks, NullCallbacks, RecordingCallbacks
from .engine import ProtocolEngine, RunMode
from .param_view import ParamView
from .registry import REGISTRY
from .specs import (
    ParamKind,
    ParamSpec,
    PlotHint,
    ProtocolSpec,
    Visibility,
    Widget,
)

__all__ = [
    # specs(纯数据)
    "ParamKind",
    "ParamSpec",
    "PlotHint",
    "ProtocolSpec",
    "Visibility",
    "Widget",
    # 引擎核心
    "ParamView",
    "EngineCallbacks",
    "NullCallbacks",
    "RecordingCallbacks",
    "REGISTRY",
    "ProtocolEngine",
    "RunMode",
]
