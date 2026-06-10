"""协议注册表 · GUI / CLI / manifest 的唯一协议来源。

设计文档 §3.2。当前 M1 阶段把现有 `protocols.wgfmu_fefet.STAGE_REGISTRY`(11 段 StageSpec)
升格成 `ProtocolSpec`(超集),`runner` 直接指向现有 `run_stage_*`,**协议逻辑零改写**。

`params` 暂留空元组 —— 逐参数 `ParamSpec` 枚举(供 GUI 表单自动生成 + `build_argparser`)
是 M1 下一步(连同 B7 模块常量提升一起做)。届时填上 `params=(...)` 即可点亮 GUI 表单,
而本文件的 `runner` 指向与执行路径不变。
"""
from __future__ import annotations

from ..protocols.wgfmu_fefet import STAGE_REGISTRY
from .specs import ProtocolSpec

# 阶段码 → (人类标题, 物理量语义)。与设计 §7 协议卡片对齐。
_META = {
    "S0": ("空夹具/抬针 smoke", "smoke"),
    "S1": ("器件只读 baseline", "baseline"),
    "E1": ("RAWD 写后延迟读", "retention"),
    "E2": ("读扰动 minimal", "read-disturb"),
    "E3W": ("脉宽扫描", "pulse-width"),
    "E3A": ("幅值扫描", "amplitude"),
    "E4": ("imprint 预偏压", "imprint"),
    "E5": ("Vg×Vd 可视窗格", "visibility"),
    "E6R": ("无扰动参考", "reference"),
    "E6D": ("半Vdd 反极性扰动-延迟", "disturb-delay"),
    "CYCLE": ("检查点耐久", "endurance"),
}


def _build_registry() -> dict[str, ProtocolSpec]:
    registry: dict[str, ProtocolSpec] = {}
    for sid, sspec in STAGE_REGISTRY.items():
        title, physics = _META.get(sid, (sid, ""))
        registry[sid] = ProtocolSpec(
            id=sid,
            title=title,
            family="WGFMU",
            physics=physics,
            description=sspec.description,
            params=(),  # TODO(M1 下一步): 枚举 ParamSpec(B7 常量提升后)供 GUI 表单 / argparser
            csv_schema="fefet_fixedcols",
            output_label=sspec.output_label,
            runner=sspec.runner,
        )
    return registry


REGISTRY: dict[str, ProtocolSpec] = _build_registry()

__all__ = ["REGISTRY"]
