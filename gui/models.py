"""GUI 跨线程传值的纯数据对象。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RunRequest:
    """一次运行请求(从 GUI 主线程传给 worker 线程,只读)。

    `params` 已是"测量表单值 ∪ 器件身份(device_id/geometry/...)";worker 会再叠加
    `wgfmu_fefet.parse_args([])` 的全量默认,保证 run_stage_* 需要的每个键都在,
    避免 ParamView 缺键 AttributeError。
    """

    stage: str
    params: dict[str, Any] = field(default_factory=dict)
    live: bool = False
    confirm: str = ""
