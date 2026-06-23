"""FeFET 适配:`fefet_fixedcols`(FIELDNAMES 固定列 CSV)的结果画法。

这是 FeFET 专有的"分析/视图"逻辑,刻意隔离在适配层,壳(PlotPanel)只按
csv_schema 查 plot_dispatch 调用它。加新存储器时新增别的适配模块即可,本文件不动。

画法:Id_mean_A vs delay_s,按 state_target(ERS/PGM)分线;delay_s 无变化(S0/S1 只读)
时退化为 vs 行序号。增量5:接受 `options`(共性壳传入的可视化开关)——
  * show_id / show_ig:Id 实线、Ig 虚线(安全量,默认不画)。
  * error_bars:用 Id_std_A 画误差棒。
轴的对数/范围/游标由壳(PlotPanel)在 plot 之后统一施加(plot-widget 级),本文件不管。

⚠ dry-run 下这些电流是 AuditBackend 的占位值(非器件数据)。是否占位由调用方
(PlotPanel)在标题/横幅标注;本函数只如实把 CSV 里的数画出来,不伪造、不补点。
"""
from __future__ import annotations

from ..plot_dispatch import register_plot

# ERS/PGM 配色(设计 §6.2 口径)
_COLOR = {"ERS": "#2659AD", "PGM": "#B80000"}
_FALLBACK_COLORS = ["#1A801A", "#8000A0", "#A06000", "#0080A0"]


@register_plot("fefet_fixedcols")
def plot_fefet_fixedcols(df, plot_widget, *, live: bool, options: dict | None = None) -> None:
    """把一份 fefet_fixedcols CSV 画到 pyqtgraph PlotWidget。

    Args:
        df: pandas.DataFrame(已 read_csv 的 FIELDNAMES 固定列)。
        plot_widget: pyqtgraph.PlotWidget。
        live: 是否真机;dry 时由壳标注占位。
        options: 可视化开关 dict(show_id/show_ig/error_bars);None=默认(只画 Id)。
    """
    import pyqtgraph as pg  # 局部 import:仅在真正画图时需要

    opts = options or {}
    show_id = opts.get("show_id", True)
    show_ig = opts.get("show_ig", False)
    error_bars = opts.get("error_bars", False)

    plot_widget.clear()
    _lg = getattr(plot_widget.plotItem, "legend", None)
    if _lg is not None:
        _lg.clear()          # clear() 不清 legend 行,重复渲染会累积旧 CSV 的条目
    else:
        plot_widget.addLegend(offset=(10, 10))
    plot_widget.showGrid(x=True, y=True, alpha=0.3)
    plot_widget.setLabel("bottom", "delay_s")
    plot_widget.setLabel("left", "I (A)")

    if df is None or len(df) == 0:
        return

    cols = set(df.columns)
    has_state = "state_target" in cols
    has_delay = "delay_s" in cols
    if "Id_mean_A" not in cols:
        return

    def _to_num(series):
        import pandas as pd
        return pd.to_numeric(series, errors="coerce")

    use_delay = False
    if has_delay:
        dvals = _to_num(df["delay_s"]).dropna().unique()
        use_delay = len(dvals) > 1
    plot_widget.setLabel("bottom", "delay_s (s)" if use_delay else "sequence #")

    groups = list(df.groupby("state_target")) if has_state else [("", df)]
    for i, (state, sub) in enumerate(groups):
        color = _COLOR.get(str(state), _FALLBACK_COLORS[i % len(_FALLBACK_COLORS)])
        yd = _to_num(sub["Id_mean_A"]).to_numpy()
        if use_delay:
            x = _to_num(sub["delay_s"]).to_numpy()
            order = x.argsort()
            x = x[order]; yd = yd[order]
        else:
            x = list(range(len(yd)))
        name = str(state) if state else "Id"
        if show_id:
            plot_widget.plot(x, yd, pen=pg.mkPen(color=color, width=2), symbol="o",
                             symbolSize=6, symbolBrush=color, name=f"{name} Id")
            if error_bars and "Id_std_A" in cols:
                err = _to_num(sub["Id_std_A"]).to_numpy()
                if use_delay:
                    err = err[order]
                plot_widget.addItem(pg.ErrorBarItem(
                    x=_as_array(x), y=yd, height=2.0 * err, pen=pg.mkPen(color=color, width=1)))
        if show_ig and "Ig_mean_A" in cols:
            yg = _to_num(sub["Ig_mean_A"]).to_numpy()
            if use_delay:
                yg = yg[order]
            plot_widget.plot(x, yg, pen=pg.mkPen(color=color, width=1, style=_dash()),
                             symbol="t", symbolSize=5, symbolBrush=None, name=f"{name} Ig")


def _reset_legend(plot_widget):
    lg = getattr(plot_widget.plotItem, "legend", None)
    if lg is not None:
        lg.clear()
    else:
        plot_widget.addLegend(offset=(10, 10))


def _main_vg_subset(df, tonum):
    """取主读点(Vg 最接近 −1.0)的子集,避免多 Vg 读点在同一 x 上叠点。"""
    if "Vg_read_V" not in df.columns:
        return df
    clean = tonum(df["Vg_read_V"]).dropna()
    if clean.empty:
        return df
    main_vg = clean.iloc[(clean + 1.0).abs().to_numpy().argmin()]
    return df[(tonum(df["Vg_read_V"]) - main_vg).abs() < 1e-9]


@register_plot("fefet_disturb_accum")
def plot_e6m_accum(df, plot_widget, *, live: bool, options: dict | None = None) -> None:
    """E6M 累积扰动:主读点 Id_mean_A vs 累积扰动次数 n_disturb,按 state 分线(N 轴宜 log)。"""
    import pandas as pd
    import pyqtgraph as pg

    opts = options or {}
    plot_widget.clear()
    _reset_legend(plot_widget)
    plot_widget.showGrid(x=True, y=True, alpha=0.3)
    plot_widget.setLabel("bottom", "n_disturb")
    plot_widget.setLabel("left", "I (A)")
    if df is None or len(df) == 0 or "Id_mean_A" not in df.columns or "n_disturb" not in df.columns:
        return

    def tonum(s):
        return pd.to_numeric(s, errors="coerce")

    base = _main_vg_subset(df, tonum)
    groups = list(base.groupby("state_target")) if "state_target" in base.columns else [("", base)]
    for i, (state, sub) in enumerate(groups):
        color = _COLOR.get(str(state), _FALLBACK_COLORS[i % len(_FALLBACK_COLORS)])
        x = tonum(sub["n_disturb"]).to_numpy()
        yd = tonum(sub["Id_mean_A"]).to_numpy()
        order = x.argsort()
        if opts.get("show_id", True):
            plot_widget.plot(x[order], yd[order], pen=pg.mkPen(color=color, width=2),
                             symbol="o", symbolSize=6, symbolBrush=color, name=f"{state} Id@N")
        if opts.get("show_ig", False) and "Ig_mean_A" in sub.columns:
            yg = tonum(sub["Ig_mean_A"]).to_numpy()
            plot_widget.plot(x[order], yg[order], pen=pg.mkPen(color=color, width=1, style=_dash()),
                             symbol="t", symbolSize=5, name=f"{state} Ig")


@register_plot("fefet_disturb_single")
def plot_e6s_single(df, plot_widget, *, live: bool, options: dict | None = None) -> None:
    """E6S 单发扰动:扰后(post 相)主读点 Id_mean_A vs 扰后延迟,按 state 分线。"""
    import pandas as pd
    import pyqtgraph as pg

    opts = options or {}
    plot_widget.clear()
    _reset_legend(plot_widget)
    plot_widget.showGrid(x=True, y=True, alpha=0.3)
    plot_widget.setLabel("bottom", "delay_after_disturb_s (s)")
    plot_widget.setLabel("left", "I (A)")
    if df is None or len(df) == 0 or "Id_mean_A" not in df.columns:
        return

    def tonum(s):
        return pd.to_numeric(s, errors="coerce")

    d = df[df["phase"] == "post"] if "phase" in df.columns else df
    if "delay_after_disturb_s" not in d.columns or len(d) == 0:
        return
    base = _main_vg_subset(d, tonum)
    groups = list(base.groupby("state_target")) if "state_target" in base.columns else [("", base)]
    for i, (state, sub) in enumerate(groups):
        color = _COLOR.get(str(state), _FALLBACK_COLORS[i % len(_FALLBACK_COLORS)])
        x = tonum(sub["delay_after_disturb_s"]).to_numpy()
        yd = tonum(sub["Id_mean_A"]).to_numpy()
        m = ~pd.isna(x)
        x = x[m]; yd = yd[m]
        if opts.get("show_id", True) and len(x):
            order = x.argsort()
            plot_widget.plot(x[order], yd[order], pen=pg.mkPen(color=color, width=2),
                             symbol="o", symbolSize=6, symbolBrush=color, name=f"{state} post")


def _dash():
    from PySide6.QtCore import Qt
    return Qt.PenStyle.DashLine


def _as_array(x):
    import numpy as np
    return np.asarray(x, dtype=float)
