"""FeFET 适配:`fefet_fixedcols`(FIELDNAMES 固定列 CSV)的结果画法。

这是 FeFET 专有的"分析/视图"逻辑,刻意隔离在适配层,壳(PlotPanel)只按
csv_schema 查 plot_dispatch 调用它。加新存储器时新增别的适配模块即可,本文件不动。

画法(初版,简版):Id_mean_A vs delay_s,按 state_target(ERS/PGM)分线;
当 delay_s 无变化(如 S0/S1 只读 baseline)时,退化为 Id_mean_A vs 行序号。
误差棒(Id_std_A)初版不画,留待迭代。

⚠ dry-run 下这些电流是 AuditBackend 的占位值(非器件数据)。是否占位由调用方
(PlotPanel)在标题/横幅标注;本函数只如实把 CSV 里的数画出来,不伪造、不补点。
"""
from __future__ import annotations

from ..plot_dispatch import register_plot

# ERS/PGM 配色(设计 §6.2 口径)
_COLOR = {"ERS": "#2659AD", "PGM": "#B80000"}
_FALLBACK_COLORS = ["#1A801A", "#8000A0", "#A06000", "#0080A0"]


@register_plot("fefet_fixedcols")
def plot_fefet_fixedcols(df, plot_widget, *, live: bool) -> None:
    """把一份 fefet_fixedcols CSV 画到 pyqtgraph PlotWidget。

    Args:
        df: pandas.DataFrame(已 read_csv 的 FIELDNAMES 固定列)。
        plot_widget: pyqtgraph.PlotWidget。
        live: 是否真机;dry 时由壳标注占位。
    """
    import pyqtgraph as pg  # 局部 import:仅在真正画图时需要

    plot_widget.clear()
    _lg = getattr(plot_widget.plotItem, "legend", None)
    if _lg is not None:
        _lg.clear()          # clear() 不清 legend 行,重复渲染会累积旧 CSV 的条目
    else:
        plot_widget.addLegend(offset=(10, 10))
    plot_widget.showGrid(x=True, y=True, alpha=0.3)
    plot_widget.setLabel("bottom", "delay_s")
    plot_widget.setLabel("left", "Id_mean_A")

    if df is None or len(df) == 0:
        return

    cols = set(df.columns)
    has_state = "state_target" in cols
    has_delay = "delay_s" in cols
    has_id = "Id_mean_A" in cols
    if not has_id:
        return

    def _to_num(series):
        import pandas as pd
        return pd.to_numeric(series, errors="coerce")

    # 判断 delay_s 是否有变化,决定 x 轴用 delay 还是行序号
    use_delay = False
    if has_delay:
        dvals = _to_num(df["delay_s"]).dropna().unique()
        use_delay = len(dvals) > 1

    groups = list(df.groupby("state_target")) if has_state else [("", df)]
    for i, (state, sub) in enumerate(groups):
        color = _COLOR.get(str(state), _FALLBACK_COLORS[i % len(_FALLBACK_COLORS)])
        pen = pg.mkPen(color=color, width=2)
        y = _to_num(sub["Id_mean_A"]).to_numpy()
        if use_delay:
            x = _to_num(sub["delay_s"]).to_numpy()
            order = x.argsort()
            x, y = x[order], y[order]
            plot_widget.setLabel("bottom", "delay_s (s)")
        else:
            x = list(range(len(y)))
            plot_widget.setLabel("bottom", "sequence #")
        name = str(state) if state else "Id"
        plot_widget.plot(x, y, pen=pen, symbol="o", symbolSize=6,
                         symbolBrush=color, name=name)
