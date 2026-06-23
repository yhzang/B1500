"""DC(SMU)适配:Id-Vg / Id-Vd 结果画法。@register_plot("dc")。

x = 变化的 Vd(Id-Vd)或 Vg(Id-Vg);y = |Id|(半对数友好,log 由壳的勾选施加,本函数只画 abs)。
签名匹配壳调用 `fn(df, plot_widget, *, live, options=None)`。
"""
from __future__ import annotations

from ..plot_dispatch import register_plot

_ID_COLOR = "#2659AD"
_IG_COLOR = "#B80000"


@register_plot("dc")
def plot_dc(df, plot_widget, *, live: bool, options: dict | None = None) -> None:
    import pandas as pd
    import pyqtgraph as pg

    plot_widget.clear()
    _lg = getattr(plot_widget.plotItem, "legend", None)
    if _lg is not None:
        _lg.clear()
    else:
        plot_widget.addLegend(offset=(10, 10))
    plot_widget.showGrid(x=True, y=True, alpha=0.3)
    plot_widget.setLabel("left", "|I| (A)")

    if df is None or len(df) == 0 or "id_A" not in df.columns:
        return

    def _num(col):
        return pd.to_numeric(df[col], errors="coerce")

    if "vd_set" in df.columns and _num("vd_set").nunique() > 1:
        x = _num("vd_set").to_numpy()
        plot_widget.setLabel("bottom", "Vd (V)")
    else:
        x = _num("vg_set").to_numpy()
        plot_widget.setLabel("bottom", "Vg (V)")

    plot_widget.plot(x, _num("id_A").abs().to_numpy(), pen=pg.mkPen(_ID_COLOR, width=2),
                     symbol="o", symbolSize=6, symbolBrush=_ID_COLOR, name="|Id|")
    opts = options or {}
    if opts.get("show_ig", False) and "ig_A" in df.columns:
        plot_widget.plot(x, _num("ig_A").abs().to_numpy(), pen=pg.mkPen(_IG_COLOR, width=1),
                         symbol="t", symbolSize=5, symbolBrush=_IG_COLOR, name="|Ig|")
    banner = "" if live else "  [DRY 占位电流 · 非器件数据]"
    plot_widget.setTitle(f"DC{banner}")
