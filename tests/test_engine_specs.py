"""engine.specs 单元测试 · 纯数据规格的契约。

只验证纯数据层的行为(可见性 → editable、as_stage_spec 兼容旧 StageSpec、
冻结不可变),不碰仪器/Qt。设计文档 §3.1。
"""
from __future__ import annotations

import dataclasses

import pytest

from fefetlab.engine import (
    ParamKind,
    ParamSpec,
    PlotHint,
    ProtocolSpec,
    Visibility,
    Widget,
)


def _p(**kw):
    base = dict(name="vd_read", label="读出 Vd", kind=ParamKind.FLOAT, default=0.05)
    base.update(kw)
    return ParamSpec(**base)


def test_editable_follows_visibility():
    assert _p(visibility=Visibility.BASIC).editable is True
    assert _p(visibility=Visibility.ADVANCED).editable is True
    assert _p(visibility=Visibility.LOCKED).editable is False


def test_paramspec_defaults():
    p = _p()
    assert p.unit == ""
    assert p.visibility is Visibility.BASIC
    assert p.widget is Widget.DOUBLE_SPINBOX
    assert p.cli_flag is None
    assert p.minimum is None and p.maximum is None


def test_paramspec_is_frozen():
    p = _p()
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.default = 0.1  # type: ignore[misc]


def test_protocolspec_as_stage_spec_matches_legacy_contract():
    def fake_runner(backend, view, *, callbacks=None):  # 形如 run_stage_*
        return None

    spec = ProtocolSpec(
        id="E1",
        title="RAWD 写后延迟读",
        family="WGFMU",
        physics="retention",
        description="RAWD delay experiment",
        params=(_p(),),
        output_label="E1_RAWD_QUICK300ms_v2",
        runner=fake_runner,
    )
    legacy = spec.as_stage_spec()
    assert legacy.name == "E1"
    assert legacy.output_label == "E1_RAWD_QUICK300ms_v2"
    assert legacy.description == "RAWD delay experiment"
    assert legacy.runner is fake_runner


def test_as_stage_spec_output_label_falls_back_to_id():
    spec = ProtocolSpec(
        id="S0", title="空夹具", family="WGFMU", physics="smoke",
        description="open/fixture smoke", params=(),
    )
    assert spec.as_stage_spec().output_label == "S0"


def test_plot_hint_holds_axes():
    h = PlotHint(schema="fefet_fixedcols", kind="mw_vs_delay", x="delay_s", y="Id_mean_A", group_by="state_target")
    assert h.x == "delay_s" and h.y == "Id_mean_A" and h.group_by == "state_target"
