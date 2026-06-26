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


def spec_from_decl(decl: DeclaredProtocol) -> ProtocolSpec:
    """单条 DeclaredProtocol → ProtocolSpec(校验 + 装 compile_declared 为 runner)。"""
    _validate(decl)
    return ProtocolSpec(
        id=decl.id, title=decl.title, family="CUSTOM", physics=decl.physics,
        description=decl.description, params=_params_from_decl(decl),
        csv_schema="fefet_fixedcols", group=decl.group,
        output_label=decl.id, runner=partial(compile_declared, decl),
    )


def default_params_for_decl(decl: DeclaredProtocol) -> dict:
    """该声明式协议的 dry 默认参数(reps/n_pts/通道/扫描/Ig 门 + 最小身份)。"""
    p = {ps.name: ps.default for ps in _params_from_decl(decl)}
    p.update(device_id="PREVIEW", geometry="L10W10", serial="",
             device_type="", operator="", seed=20260603, live=False)
    return p


# 内置声明式协议 id(family 也是 CUSTOM,但属内置、用户配方不得占用/覆盖)
_BUILTIN_DECLARED_IDS = frozenset(d.id for d in DECLARED_PROTOCOLS)


def is_reserved_builtin_id(rid: str) -> bool:
    """该 id 是否属于内置协议(WGFMU/SMU 或内置声明式)——用户配方不得占用/覆盖。"""
    if rid in _BUILTIN_DECLARED_IDS:
        return True
    from ...engine.registry import REGISTRY

    spec = REGISTRY.get(rid)
    return spec is not None and spec.family != "CUSTOM"


def custom_recipe_ids() -> list[str]:
    """当前 REGISTRY 里"用户自定义"协议 id(CUSTOM 族且非内置声明式),供删除/列举用。"""
    from ...engine.registry import REGISTRY

    return [sid for sid, sp in REGISTRY.items()
            if sp.family == "CUSTOM" and sid not in _BUILTIN_DECLARED_IDS]


def build_declared_specs() -> dict[str, ProtocolSpec]:
    from .user_store import load_recipes

    out: dict[str, ProtocolSpec] = {}
    for decl in DECLARED_PROTOCOLS:                 # 内置:坏就该炸(测试覆盖)
        out[decl.id] = spec_from_decl(decl)
    for decl in load_recipes():                     # 用户配方:坏的跳过,且不准覆盖内置声明式
        if decl.id in out:
            continue
        try:
            out[decl.id] = spec_from_decl(decl)
        except Exception:  # noqa: BLE001
            continue
    return out


def register_recipe(decl: DeclaredProtocol) -> ProtocolSpec:
    """把一条配方即时注册进 REGISTRY(GUI 新建后免重启)。拒绝占用内置 id。"""
    from ...engine.registry import REGISTRY

    if is_reserved_builtin_id(decl.id):
        raise ValueError(f"{decl.id} 是内置协议 id,自定义配方不能占用")
    spec = spec_from_decl(decl)
    REGISTRY[decl.id] = spec
    return spec


def unregister_recipe(recipe_id: str) -> bool:
    """从 REGISTRY 移除一条自定义协议(仅限 CUSTOM 族且非内置声明式)。返回是否移除。"""
    from ...engine.registry import REGISTRY

    if recipe_id in custom_recipe_ids():
        del REGISTRY[recipe_id]
        return True
    return False
