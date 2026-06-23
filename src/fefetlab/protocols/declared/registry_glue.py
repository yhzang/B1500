"""把 library 的 DeclaredProtocol 转成 ProtocolSpec(+ParamSpec),供 registry 末尾纯加法注册。

family="CUSTOM"、独立 group、cli_flag=None(守门 argparse 比对自动跳过)、不进 ALL_DRY/STAGES
→ 与 WGFMU/SMU 完全隔离,绝不碰 golden。加载期校验:read 必须末尾、scan step_index 合法。
"""
from __future__ import annotations

from functools import partial

from ...engine.specs import ParamKind as K
from ...engine.specs import ParamSpec, ProtocolSpec
from ...engine.specs import Visibility as V
from ...engine.specs import Widget as W
from ..wgfmu_fefet import DRAIN_CH, GATE_CH, N_PTS
from .compiler import compile_declared
from .library import DECLARED_PROTOCOLS
from .schema import DeclaredProtocol, ReadStep


def _cp(name, kind, default, *, label, unit="", vis=V.BASIC, widget=W.DOUBLE_SPINBOX,
        minimum=None, help=""):
    # cli_flag=None:GUI/引擎专用,不进 WGFMU CLI → test_registry_params 的 argparse 比对自动跳过
    return ParamSpec(name=name, label=label, kind=kind, default=default, unit=unit,
                     visibility=vis, minimum=minimum, maximum=None, choices=None,
                     widget=widget, cli_flag=None, help=help)


def _validate(decl: DeclaredProtocol) -> None:
    if not decl.steps or not isinstance(decl.steps[-1], ReadStep):
        raise ValueError(f"声明式协议 {decl.id}: 末尾必须是 read step")
    if decl.scan_axis is not None and not (0 <= decl.scan_axis.step_index < len(decl.steps)):
        raise ValueError(f"声明式协议 {decl.id}: scan_axis.step_index 越界")


def _params_from_decl(decl: DeclaredProtocol) -> tuple[ParamSpec, ...]:
    ps = [
        _cp("reps", K.INT, decl.reps, label="重复次数", vis=V.BASIC, widget=W.SPINBOX, minimum=1),
        _cp("n_pts", K.INT, N_PTS, label="每窗采样点", vis=V.ADVANCED, widget=W.SPINBOX, minimum=1),
        _cp("gate_ch", K.INT, GATE_CH, label="Gate 通道", vis=V.LOCKED, widget=W.CHANNEL,
            help="接线铁律,只读"),
        _cp("drain_ch", K.INT, DRAIN_CH, label="Drain 通道", vis=V.LOCKED, widget=W.CHANNEL,
            help="接线铁律,只读"),
    ]
    if decl.scan_axis is not None:
        ps.append(_cp(decl.scan_axis.label, K.FLOAT_LIST,
                      ",".join(str(x) for x in decl.scan_axis.values),
                      label=f"扫描:{decl.scan_axis.label}", widget=W.CSV_LINE,
                      help="扫描轴取值(逗号分隔),可改"))
    if decl.stop_gate is not None:
        ps.append(_cp(f"{decl.id}_ig_stop_uA", K.FLOAT, decl.stop_gate.ig_stop_uA,
                      label="Ig 停门", unit="µA", vis=V.ADVANCED, minimum=0.0))
    return tuple(ps)


def build_declared_specs() -> dict[str, ProtocolSpec]:
    out: dict[str, ProtocolSpec] = {}
    for decl in DECLARED_PROTOCOLS:
        _validate(decl)
        out[decl.id] = ProtocolSpec(
            id=decl.id, title=decl.title, family="CUSTOM", physics=decl.physics,
            description=decl.description, params=_params_from_decl(decl),
            csv_schema="fefet_fixedcols", group=decl.group,
            output_label=decl.id, runner=partial(compile_declared, decl),
        )
    return out
