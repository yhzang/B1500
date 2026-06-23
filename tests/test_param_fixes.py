"""参数设置 bug 修复回归:自适应小数位、电压夹值、整数列表拒空/拒非正、非法即拒下发。"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from fefetlab.engine.specs import ParamKind, ParamSpec, ProtocolSpec


def _w(form, name):
    for p, wdg in form._fields:
        if p.name == name:
            return p, wdg
    raise KeyError(name)


def _spec(*params):
    return ProtocolSpec(id="X", title="t", family="WGFMU", physics="p",
                        description="d", params=tuple(params))


def test_adaptive_decimals_step():
    from gui.param_form import _adaptive_decimals_step

    d, s = _adaptive_decimals_step(1e-5)
    assert d == 8 and abs(s - 1e-6) < 1e-18
    assert _adaptive_decimals_step(100.0)[0] == 3
    assert _adaptive_decimals_step(1e-7)[0] >= 9   # 极小值要足够小数位才不被清零


def test_tiny_seconds_not_zeroed(qapp):
    """unit='s' 的极小默认值(5e-7)不被 6 位小数静默清零,round-trip 还原。"""
    from PySide6.QtWidgets import QDoubleSpinBox

    from gui.param_form import ParamForm

    form = ParamForm()
    form.set_protocol(_spec(ParamSpec(name="d_s", label="延迟", kind=ParamKind.FLOAT,
                                      default=5e-7, unit="s")))
    _p, w = _w(form, "d_s")
    assert isinstance(w, QDoubleSpinBox)
    assert abs(form.collect()["d_s"] - 5e-7) < 1e-13   # 旧 6 位小数会清零/round 成 1e-6


def test_voltage_spinbox_clamped(qapp):
    from gui.param_form import ParamForm

    form = ParamForm()
    form.set_protocol(_spec(ParamSpec(name="v", label="幅值", kind=ParamKind.FLOAT,
                                      default=2.0, unit="V")))
    _p, w = _w(form, "v")
    assert w.maximum() <= 10.0 + 1e-6 and w.minimum() >= -10.0 - 1e-6


def test_nullable_voltage_over_limit_invalid(qapp):
    from gui.param_form import ParamForm

    form = ParamForm()
    form.set_protocol(_spec(ParamSpec(name="wv", label="写压", kind=ParamKind.FLOAT,
                                      default=None, unit="V")))
    _p, w = _w(form, "wv")
    w.setText("50")
    assert form.is_valid() is False
    with pytest.raises(ValueError):
        form.collect()
    w.setText("5")
    assert form.is_valid() is True
    assert abs(form.collect()["wv"] - 5.0) < 1e-9


def test_int_list_rejects_empty_and_negative(qapp):
    from gui.param_form import ParamForm

    form = ParamForm()
    form.set_protocol(_spec(ParamSpec(name="ckpt", label="检查点", kind=ParamKind.INT_LIST,
                                      default="1,10,100")))
    _p, w = _w(form, "ckpt")
    w.setText("")
    assert form.is_valid() is False           # 空非法
    w.setText("10,-5")
    assert form.is_valid() is False           # 非正非法
    w.setText("10,100,1000")
    assert form.is_valid() is True


def test_float_list_still_allows_negatives(qapp):
    """浮点列表(扰动幅度/电压)允许负值,不被整数列表的拒负误伤。"""
    from gui.param_form import ParamForm

    form = ParamForm()
    form.set_protocol(_spec(ParamSpec(name="amps", label="幅度", kind=ParamKind.FLOAT_LIST,
                                      default="1.33,2.0")))
    _p, w = _w(form, "amps")
    w.setText("-2.0,1.33")
    assert form.is_valid() is True
