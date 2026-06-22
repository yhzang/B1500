"""PlotPanel · 编程波形预览 + 结果图 + 逐炮实时增量图(共性壳)。

三种绘制:
  * 编程波形(show_waveform):dry 跑完后从 AuditBackend._patterns 取出的 gate/drain 向量
    (这是**真实将要下发的电压意图**,不是伪造数据),逐段 piecewise-linear 画出。
  * 逐炮实时(begin_live_plot / append_shot_rows):每炮 on_shot 来一组 rows,增量追加进
    结果图——跑的时候就能看见曲线一点点长出来,而不是跑完才出。环形缓冲 + 30fps QTimer
    限频(不每炮重画)+ >4000 点降采样。目前只对 `fefet_fixedcols`(Id_mean_A vs delay_s,
    按 state_target 分线)有实时映射;其它 schema 退化为只在跑完出结果图。
  * 结果图(show_result):跑完按 ProtocolSpec.csv_schema 查 plot_dispatch,从落盘 CSV
    重读重画(权威终图,与磁盘一致)。

dry-run 横幅:实时/结果图标题强制标注 "DRY 占位电流(非器件数据)",守住"不拿占位当结果"。
pyqtgraph 缺失时整体降级为提示文字(本机不装、测试机才装)。
"""
from __future__ import annotations

from math import ceil
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from .plot_dispatch import get_plotter

try:
    import pyqtgraph as pg

    HAVE_PG = True
except Exception:  # noqa: BLE001
    HAVE_PG = False

# 实时图配色(与 fefet_plots.py 同口径,设计 §6.2:ERS 蓝 / PGM 红)
_LIVE_COLOR = {"ERS": "#2659AD", "PGM": "#B80000"}
_LIVE_FALLBACK = ["#1A801A", "#8000A0", "#A06000", "#0080A0"]
_LIVE_SCHEMAS = {"fefet_fixedcols"}  # 目前只有它有逐炮 → 点 的实时映射
_MAX_LIVE_POINTS = 4000  # 显示降采样上限(底层缓冲不丢)


class PlotPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tabs = QTabWidget()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.addWidget(self.tabs)

        # 实时增量状态(begin_live_plot 重置)
        self._live_active = False
        self._live_live = False
        self._live_buffers: dict[str, tuple[list, list]] = {}
        self._live_items: dict = {}
        self._live_dirty = False
        self._live_timer: QTimer | None = None

        if not HAVE_PG:
            self._wave = None
            self._result = None
            self.tabs.addTab(_missing_label(), "编程波形")
            self.tabs.addTab(_missing_label(), "结果图")
            return

        self._wave = pg.PlotWidget()
        self._wave.addLegend(offset=(10, 10))
        self._wave.showGrid(x=True, y=True, alpha=0.3)
        self._wave.setLabel("bottom", "time (ms)")
        self._wave.setLabel("left", "V")
        self._result = pg.PlotWidget()
        self._result.showGrid(x=True, y=True, alpha=0.3)
        self.tabs.addTab(self._wave, "编程波形")
        self.tabs.addTab(self._result, "结果图")

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(33)  # ~30 fps:合并多炮一次刷新,不每炮重画
        self._live_timer.timeout.connect(self._flush_live)

    # ── 编程波形 ──────────────────────────────────────────────────────────────
    def show_waveform(self, patterns: list[dict]) -> None:
        """patterns: [{'name': 'gp', 'x': [...s], 'y': [...V]}, ...](x 单位秒)。"""
        if not HAVE_PG or self._wave is None:
            return
        self._wave.clear()
        _lg = getattr(self._wave.plotItem, "legend", None)
        if _lg is not None:
            _lg.clear()          # clear() 不清 legend 行,重复运行会累积重复条目
        else:
            self._wave.addLegend(offset=(10, 10))
        # 取自跑完后的 backend._patterns —— 每炮开头会 clear,故这里是**最后一炮**的波形
        self._wave.setTitle("编程波形(最后一炮)")
        colors = ["#2659AD", "#B80000", "#1A801A", "#8000A0"]
        for i, pat in enumerate(patterns or []):
            x = [t * 1e3 for t in pat.get("x", [])]  # s → ms
            y = list(pat.get("y", []))
            if not x:
                continue
            pen = pg.mkPen(color=colors[i % len(colors)], width=2)
            self._wave.plot(x, y, pen=pen, name=str(pat.get("name", f"ch{i}")))
        self.tabs.setCurrentIndex(0)

    # ── 逐炮实时增量 ──────────────────────────────────────────────────────────
    def begin_live_plot(self, schema: str, *, live: bool = False) -> None:
        """新一次运行开始时调:清结果图、重置实时缓冲。仅对支持的 schema 真正启用实时。"""
        if not HAVE_PG or self._result is None:
            return
        self._live_buffers.clear()
        self._live_items.clear()
        self._live_dirty = False
        self._live_live = bool(live)
        self._live_active = schema in _LIVE_SCHEMAS
        if not self._live_active:
            return
        self._result.clear()
        _lg = getattr(self._result.plotItem, "legend", None)
        if _lg is not None:
            _lg.clear()
        else:
            self._result.addLegend(offset=(10, 10))
        self._result.showGrid(x=True, y=True, alpha=0.3)
        self._result.setLabel("bottom", "delay_s (s)")
        self._result.setLabel("left", "Id_mean_A")
        banner = "" if live else "  [DRY 占位电流 · 非器件数据]"
        self._result.setTitle(f"实时(逐炮){banner}")
        self.tabs.setCurrentIndex(1)
        if self._live_timer is not None:
            self._live_timer.start()

    def append_shot_rows(self, stage: str, seq: int, rows) -> None:
        """每炮 on_shot 的 rows(fefet_fixedcols dict 行)增量入缓冲;由 QTimer 限频刷新。"""
        if not self._live_active or not rows:
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            y = _to_float(row.get("Id_mean_A"))
            if y is None:
                continue
            state = str(row.get("state_target", "") or "Id")
            bx, by = self._live_buffers.setdefault(state, ([], []))
            x = _to_float(row.get("delay_s"))
            bx.append(x if x is not None else float(len(bx)))
            by.append(y)
        self._live_dirty = True

    def _flush_live(self) -> None:
        if not self._live_active or not self._live_dirty or self._result is None:
            return
        self._live_dirty = False
        for i, (state, (bx, by)) in enumerate(sorted(self._live_buffers.items())):
            color = _LIVE_COLOR.get(state, _LIVE_FALLBACK[i % len(_LIVE_FALLBACK)])
            item = self._live_items.get(state)
            if item is None:
                item = self._result.plot([], [], pen=pg.mkPen(color=color, width=2),
                                         symbol="o", symbolSize=6, symbolBrush=color,
                                         name=state)
                self._live_items[state] = item
            xs, ys = _sorted_downsampled(bx, by)
            item.setData(xs, ys)

    # ── 结果图(权威终图;停实时计时器) ───────────────────────────────────────
    def show_result(self, csv_path, schema: str, *, live: bool) -> None:
        if not HAVE_PG or self._result is None:
            return
        # 跑完:停实时刷新,改由落盘 CSV 重画一遍(以磁盘为准)
        if self._live_timer is not None:
            self._live_timer.stop()
        self._live_active = False
        self._result.clear()
        try:
            import pandas as pd
        except Exception:  # noqa: BLE001
            self._result.setTitle("pandas 未安装,无法读 CSV")
            return
        p = Path(csv_path)
        if not p.exists():
            self._result.setTitle(f"找不到结果 CSV: {p}")
            return
        try:
            df = pd.read_csv(p)
        except Exception as exc:  # noqa: BLE001
            self._result.setTitle(f"读 CSV 失败: {exc}")
            return
        plotter = get_plotter(schema)
        if plotter is None:
            self._result.setTitle(f"schema '{schema}' 暂无绘图器(在 gui/adapters 注册)")
            return
        try:
            plotter(df, self._result, live=live)
        except Exception as exc:  # noqa: BLE001
            self._result.setTitle(f"绘图失败: {exc}")
            return
        banner = "" if live else "  [DRY 占位电流 · 非器件数据]"
        self._result.setTitle(f"{p.name}{banner}")
        self.tabs.setCurrentIndex(1)


def _to_float(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _sorted_downsampled(bx: list, by: list) -> tuple[list, list]:
    pairs = sorted(zip(bx, by), key=lambda pt: pt[0])
    n = len(pairs)
    if n > _MAX_LIVE_POINTS:
        stride = ceil(n / _MAX_LIVE_POINTS)
        pairs = pairs[::stride]
    return [pt[0] for pt in pairs], [pt[1] for pt in pairs]


def _missing_label() -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel("未安装 pyqtgraph —— 在测试机:\npip install -r requirements/gui.txt"))
    return w
