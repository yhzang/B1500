"""坐实"加新存储器只补适配层、gui/ 壳一行不改"这条缝。

设计依据:`_agent/references/B1500_GUI架构设计_PySide6.md` §2 共性壳/适配层、
M2 计划 §9.5。做法:临时往 REGISTRY 注册一个假的新 family(RRAM)协议 + 给它的
csv_schema 注册一个绘图器,再构造**真实的** ProtocolPanel / PlotPanel,断言:

  * 协议树自动多出 RRAM 分组与该协议(ProtocolPanel 按 family 泛化,未硬编码协议码);
  * 新 csv_schema 经 plot_dispatch 路由到新绘图器(壳只认 schema 字符串,不认 FeFET)。

全程不改 gui/ 任何文件。fixture 在 yield 后清理注册表/分派表,绝不污染其它测试。
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from fefetlab.engine import REGISTRY
from fefetlab.engine.specs import ParamKind, ParamSpec, ProtocolSpec, Visibility

_FAKE_ID = "RRAM_FORMING"
_FAKE_FAMILY = "RRAM"
_FAKE_SCHEMA = "rram_iv_demo"


def _fake_spec() -> ProtocolSpec:
    return ProtocolSpec(
        id=_FAKE_ID,
        title="Forming 成形(演示扩展)",
        family=_FAKE_FAMILY,
        physics="forming",
        description="假协议:仅验证扩展缝,不接 runner",
        params=(
            ParamSpec(name="v_form", label="成形电压", kind=ParamKind.FLOAT,
                      default=3.0, unit="V", visibility=Visibility.BASIC),
            ParamSpec(name="i_comp_uA", label="限流", kind=ParamKind.FLOAT,
                      default=10.0, unit="µA", visibility=Visibility.ADVANCED),
        ),
        csv_schema=_FAKE_SCHEMA,
    )


@pytest.fixture()
def fake_family(qapp):
    """注册假 family + 绘图器,yield 后无痕清理。"""
    from gui.plot_dispatch import PLOT_DISPATCH, register_plot

    spec = _fake_spec()
    REGISTRY[_FAKE_ID] = spec

    @register_plot(_FAKE_SCHEMA)
    def _plot_rram(df, plot_widget, *, live: bool, options=None):  # noqa: ANN001
        try:
            plot_widget.plot([0, 1, 2], [1.0, 2.0, 3.0])
        except Exception:  # noqa: BLE001
            pass

    try:
        yield spec
    finally:
        REGISTRY.pop(_FAKE_ID, None)
        PLOT_DISPATCH.pop(_FAKE_SCHEMA, None)


def test_protocol_tree_auto_shows_new_family(fake_family):
    """加一个新 family 的 ProtocolSpec → 协议树自动多出该分组,gui/ 不改。"""
    from PySide6.QtCore import Qt

    from gui.protocol_panel import ProtocolPanel

    panel = ProtocolPanel()
    families = {panel.tree.topLevelItem(i).text(0)
                for i in range(panel.tree.topLevelItemCount())}
    assert _FAKE_FAMILY in families, f"新 family 未出现在协议树:{families}"

    # 找到 RRAM 分组下叶子,选中 → ParamForm 渲染其参数
    leaf = None
    for i in range(panel.tree.topLevelItemCount()):
        grp = panel.tree.topLevelItem(i)
        for j in range(grp.childCount()):
            ch = grp.child(j)
            if ch.data(0, Qt.ItemDataRole.UserRole) == _FAKE_ID:
                leaf = ch
    assert leaf is not None, "未找到 RRAM 协议叶子节点"
    panel.tree.setCurrentItem(leaf)
    out = panel.collect_params()
    assert "v_form" in out and "i_comp_uA" in out


def test_plot_dispatch_routes_new_schema(fake_family, tmp_path):
    """新 csv_schema 注册一个绘图器 → PlotPanel 按 schema 查表分派,壳不认 FeFET。"""
    pytest.importorskip("pyqtgraph")
    import pandas as pd

    from gui.plot_dispatch import get_plotter
    from gui.plot_panel import PlotPanel

    assert get_plotter(_FAKE_SCHEMA) is not None

    pp = PlotPanel()
    csv = tmp_path / "rram.csv"
    pd.DataFrame({"cycle": [0, 1, 2], "R_ohm": [1e3, 2e3, 3e3]}).to_csv(csv, index=False)
    pp.show_result(str(csv), _FAKE_SCHEMA, live=False)  # 不抛 = 分派成功


def test_shell_has_no_fefet_hardcode():
    """壳层(gui/ 顶层,排除 adapters/)不得出现 FeFET 协议码硬编码,保证泛化。

    白名单:'fefet' 词出现在注释/文档/schema 字符串里允许(如 'fefet_fixedcols'
    作为默认 csv_schema 引用);但不得出现按具体协议码特判(if pid == 'E1')。
    本测试做一个弱保证:壳层不 import adapters.fefet_plots、不写死 'E1'/'CYCLE' 等码。
    """
    import pathlib

    shell_dir = pathlib.Path(__file__).resolve().parent.parent / "gui"
    bad = []
    hardcoded_ids = ("== \"E1\"", "=='E1'", "== 'E1'", "\"CYCLE\":", "'S0','S1'")
    for py in shell_dir.glob("*.py"):  # 只查壳层顶层,不进 adapters/
        text = py.read_text(encoding="utf-8")
        for token in hardcoded_ids:
            if token in text:
                bad.append((py.name, token))
    assert not bad, f"壳层出现协议码硬编码(应按 family/schema 泛化):{bad}"
