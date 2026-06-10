"""fefetlab 引擎核心 (headless,零 Qt)。

设计文档 §3。把现状(1378 行 WGFMU CLI + DC API + orchestration 层)收口成一个
GUI 与 CLI 共用的协议引擎内核。本包刻意不依赖 Qt,可被 CLI / 测试直接调用。

M1 渐进落地中,当前已就位:
  * specs       —— 唯一权威 ParamSpec / ProtocolSpec / PlotHint(纯数据,§3.1)

后续(§3.2–3.7)将补:registry / engine / param_view / backend_manager / callbacks。
"""
from .specs import (
    ParamKind,
    ParamSpec,
    PlotHint,
    ProtocolSpec,
    Visibility,
    Widget,
)

__all__ = [
    "ParamKind",
    "ParamSpec",
    "PlotHint",
    "ProtocolSpec",
    "Visibility",
    "Widget",
]
