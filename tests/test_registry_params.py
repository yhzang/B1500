"""M1 · REGISTRY ParamSpec 枚举一致性守门。

证明 `engine.REGISTRY` 里每个协议的 `params` 与 `wgfmu_fefet.parse_args` 的**真实
flag/默认值**一字不差(name==argparse dest、default==argparse default),且 11 段都
非空——这是"GUI 表单自动生成料"的正确性闸:一旦有人改了 argparse 默认却忘了同步
ParamSpec(或反之),这里立刻红。
"""
from __future__ import annotations

from fefetlab.engine import REGISTRY
from fefetlab.engine.specs import ParamKind, Visibility, Widget
from fefetlab.protocols.wgfmu_fefet import parse_args

STAGES = ["S0", "S1", "E1", "E2", "E3W", "E3A", "E4", "E5", "E6R", "E6D", "CYCLE", "MLC"]


def _argparse_defaults() -> dict:
    """dest -> 默认值(不传 --stage 即全默认;configure_channel_map 不在 parse_args 内,安全)。"""
    return vars(parse_args([]))


def _all_specs():
    for sid in STAGES:
        for p in REGISTRY[sid].params:
            yield sid, p


def test_registry_covers_eleven_stages_each_nonempty():
    assert set(REGISTRY) == set(STAGES)
    for sid in STAGES:
        assert REGISTRY[sid].params, f"{sid} 的 params 为空"


def test_paramspec_name_matches_derived_cli_dest():
    for sid, p in _all_specs():
        if p.cli_flag is None:
            continue
        dest = p.cli_flag.lstrip("-").replace("-", "_")
        assert p.name == dest, f"{sid}: name={p.name!r} 与 dest={dest!r} 不一致"


def test_paramspec_cli_flag_is_real_and_default_matches_argparse():
    defaults = _argparse_defaults()
    for sid, p in _all_specs():
        if p.cli_flag is None:
            continue
        assert p.name in defaults, f"{sid}: {p.name!r} 不是 parse_args 的真实 flag"
        assert p.default == defaults[p.name], (
            f"{sid}: {p.name} default={p.default!r} ≠ argparse {defaults[p.name]!r}"
        )


def test_paramspec_kinds_and_widgets_are_valid_enums():
    for sid, p in _all_specs():
        assert isinstance(p.kind, ParamKind), f"{sid}:{p.name} kind 非法"
        assert isinstance(p.visibility, Visibility), f"{sid}:{p.name} visibility 非法"
        assert isinstance(p.widget, Widget), f"{sid}:{p.name} widget 非法"


def test_channels_are_locked_wiring_invariants():
    # Gate/Drain 通道是接线铁律,GUI 必须 LOCKED(只读/二次确认),错值打错电极。
    for sid in STAGES:
        by_name = {p.name: p for p in REGISTRY[sid].params}
        assert by_name["gate_ch"].visibility is Visibility.LOCKED
        assert by_name["drain_ch"].visibility is Visibility.LOCKED
        assert by_name["gate_ch"].widget is Widget.CHANNEL
