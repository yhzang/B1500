"""绘图分派注册表(共性壳的"接缝件")。

壳里 `PlotPanel` 永远只按 `ProtocolSpec.csv_schema` 查这张表来画结果图,
**不把任何存储器专有画法写死在壳里**。FeFET 的画法用 `@register_plot("fefet_fixedcols")`
注册(住在 `gui/adapters/fefet_plots.py`);将来加 RRAM 只需新增
`@register_plot("rram_iv")`,壳一行不改。

绘图函数签名:`fn(df: pandas.DataFrame, plot_widget, *, live: bool) -> None`
其中 `plot_widget` 是 pyqtgraph 的 PlotWidget(由 PlotPanel 传入)。
"""
from __future__ import annotations

from typing import Callable

PlotFn = Callable[..., None]

PLOT_DISPATCH: dict[str, PlotFn] = {}


def register_plot(schema: str) -> Callable[[PlotFn], PlotFn]:
    """装饰器:把某 csv_schema 的画法登记进分派表。"""

    def deco(fn: PlotFn) -> PlotFn:
        PLOT_DISPATCH[schema] = fn
        return fn

    return deco


def get_plotter(schema: str) -> PlotFn | None:
    return PLOT_DISPATCH.get(schema)
