"""PlotPanel · 编程波形预览 + 结果图(可视化进阶) + 逐炮实时增量图(共性壳)。

三种绘制:
  * 编程波形(show_waveform):dry 跑完从 AuditBackend._patterns 取出的 gate/drain 电压意图。
  * 逐炮实时(begin_live_plot / append_shot_rows):每炮 on_shot 增量追加进结果图(环形缓冲 +
    30fps QTimer 限频 + >4000 点降采样)。仅 fefet_fixedcols 有实时映射。
  * 结果图(show_result):跑完按 csv_schema 查 plot_dispatch 从落盘 CSV 重读重画(权威终图)。

增量5 可视化进阶(结果图工具条):log X/Y 轴、Id/Ig 通道显隐、Id_std 误差棒、自动缩放、
十字游标读坐标。数据级开关(Id/Ig/误差棒)经 options 传给适配器;轴级(log/缩放/游标)由本壳
在 plot 之后统一施加。结果 df 缓存,改开关即重画,不重读 CSV。

dry-run 横幅:实时/结果图标题强制标注 "DRY 占位电流(非器件数据)"。
pyqtgraph 缺失时整体降级为提示文字(本机不装、测试机才装)。
"""
from __future__ import annotations

from math import ceil
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .plot_dispatch import get_plotter

try:
    import pyqtgraph as pg

    HAVE_PG = True
except Exception:  # noqa: BLE001
    HAVE_PG = False

_LIVE_COLOR = {"ERS": "#2659AD", "PGM": "#B80000"}
_LIVE_FALLBACK = ["#1A801A", "#8000A0", "#A06000", "#0080A0"]
_LIVE_SCHEMAS = {"fefet_fixedcols"}
_MAX_LIVE_POINTS = 4000


class PlotPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tabs = QTabWidget()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.addWidget(self.tabs)

        # 实时增量状态
        self._live_active = False
        self._live_live = False
        self._live_buffers: dict[str, tuple[list, list]] = {}
        self._live_items: dict = {}
        self._live_dirty = False
        self._live_timer: QTimer | None = None
        # 结果图缓存(改可视化开关时重画,不重读 CSV)
        self._last_result: tuple | None = None  # (df, schema, live)
        self._cursor_lines: tuple | None = None
        self._cursor_label = None

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
        self.tabs.addTab(self._build_result_tab(), "结果图")

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(33)
        self._live_timer.timeout.connect(self._flush_live)

    # ── 结果图工具条(增量5) ───────────────────────────────────────────────────
    def _build_result_tab(self) -> QWidget:
        bar = QHBoxLayout()
        self._cb_logx = QCheckBox("log X")
        self._cb_logy = QCheckBox("log Y")
        self._cb_id = QCheckBox("Id"); self._cb_id.setChecked(True)
        self._cb_ig = QCheckBox("Ig")
        self._cb_err = QCheckBox("误差棒")
        self._cb_cursor = QCheckBox("十字游标")
        self._btn_auto = QPushButton("自动缩放")
        for w in (self._cb_logx, self._cb_logy, self._cb_id, self._cb_ig, self._cb_err, self._cb_cursor):
            bar.addWidget(w)
        bar.addWidget(self._btn_auto)
        bar.addStretch(1)
        self._cb_logx.toggled.connect(self._apply_axes)
        self._cb_logy.toggled.connect(self._apply_axes)
        self._cb_id.toggled.connect(self._replot_result)
        self._cb_ig.toggled.connect(self._replot_result)
        self._cb_err.toggled.connect(self._replot_result)
        self._cb_cursor.toggled.connect(self._toggle_cursor)
        self._btn_auto.clicked.connect(lambda: self._result.enableAutoRange())

        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(2, 2, 2, 2)
        v.addLayout(bar)
        v.addWidget(self._result)
        return box

    def _viz_options(self) -> dict:
        return {"show_id": self._cb_id.isChecked(),
                "show_ig": self._cb_ig.isChecked(),
                "error_bars": self._cb_err.isChecked()}

    def _apply_axes(self) -> None:
        if self._result is not None:
            self._result.setLogMode(x=self._cb_logx.isChecked(), y=self._cb_logy.isChecked())

    def _toggle_cursor(self, on: bool) -> None:
        if self._result is None:
            return
        if on and self._cursor_lines is None:
            vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#888", width=1))
            hline = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#888", width=1))
            self._result.addItem(vline, ignoreBounds=True)
            self._result.addItem(hline, ignoreBounds=True)
            self._cursor_label = pg.TextItem(color="#333")
            self._result.addItem(self._cursor_label, ignoreBounds=True)
            self._cursor_lines = (vline, hline)
            self._result.scene().sigMouseMoved.connect(self._on_mouse_moved)
        elif not on and self._cursor_lines is not None:
            try:
                self._result.scene().sigMouseMoved.disconnect(self._on_mouse_moved)
            except (TypeError, RuntimeError):
                pass
            for it in (*self._cursor_lines, self._cursor_label):
                self._result.removeItem(it)
            self._cursor_lines = None
            self._cursor_label = None

    def _on_mouse_moved(self, pos) -> None:
        if self._cursor_lines is None:
            return
        vb = self._result.plotItem.vb
        if not self._result.plotItem.sceneBoundingRect().contains(pos):
            return
        pt = vb.mapSceneToView(pos)
        self._cursor_lines[0].setPos(pt.x())
        self._cursor_lines[1].setPos(pt.y())
        if self._cursor_label is not None:
            self._cursor_label.setText(f"x={pt.x():.4g}  y={pt.y():.3e}")
            self._cursor_label.setPos(pt.x(), pt.y())

    # ── 编程波形 ──────────────────────────────────────────────────────────────
    def show_waveform(self, patterns: list[dict]) -> None:
        if not HAVE_PG or self._wave is None:
            return
        self._wave.clear()
        _lg = getattr(self._wave.plotItem, "legend", None)
        if _lg is not None:
            _lg.clear()
        else:
            self._wave.addLegend(offset=(10, 10))
        self._wave.setTitle("编程波形(最后一炮)")
        colors = ["#2659AD", "#B80000", "#1A801A", "#8000A0"]
        for i, pat in enumerate(patterns or []):
            x = [t * 1e3 for t in pat.get("x", [])]
            y = list(pat.get("y", []))
            if not x:
                continue
            pen = pg.mkPen(color=colors[i % len(colors)], width=2)
            self._wave.plot(x, y, pen=pen, name=str(pat.get("name", f"ch{i}")))
        self.tabs.setCurrentIndex(0)

    # ── 逐炮实时增量 ──────────────────────────────────────────────────────────
    def begin_live_plot(self, schema: str, *, live: bool = False) -> None:
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
        self._apply_axes()
        if self._live_timer is not None:
            self._live_timer.start()

    def append_shot_rows(self, stage: str, seq: int, rows) -> None:
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
                                         symbol="o", symbolSize=6, symbolBrush=color, name=state)
                self._live_items[state] = item
            xs, ys = _sorted_downsampled(bx, by)
            item.setData(xs, ys)

    # ── 结果图(权威终图;停实时计时器) ───────────────────────────────────────
    def show_result(self, csv_path, schema: str, *, live: bool) -> None:
        if not HAVE_PG or self._result is None:
            return
        if self._live_timer is not None:
            self._live_timer.stop()
        self._live_active = False
        try:
            import pandas as pd
        except Exception:  # noqa: BLE001
            self._result.clear(); self._result.setTitle("pandas 未安装,无法读 CSV")
            return
        p = Path(csv_path)
        if not p.exists():
            self._result.clear(); self._result.setTitle(f"找不到结果 CSV: {p}")
            return
        try:
            df = pd.read_csv(p)
        except Exception as exc:  # noqa: BLE001
            self._result.clear(); self._result.setTitle(f"读 CSV 失败: {exc}")
            return
        self._last_result = (df, schema, live)
        self._draw_result(title=p.name)

    def _replot_result(self) -> None:
        """改可视化开关时,用缓存 df 重画(不重读 CSV)。"""
        if self._last_result is None:
            return
        self._draw_result(title=None)

    def _draw_result(self, *, title: str | None) -> None:
        df, schema, live = self._last_result
        self._result.clear()
        plotter = get_plotter(schema)
        if plotter is None:
            self._result.setTitle(f"schema '{schema}' 暂无绘图器(在 gui/adapters 注册)")
            return
        try:
            plotter(df, self._result, live=live, options=self._viz_options())
        except TypeError:
            plotter(df, self._result, live=live)  # 兼容未升级 options 的旧适配器
        except Exception as exc:  # noqa: BLE001
            self._result.setTitle(f"绘图失败: {exc}")
            return
        banner = "" if live else "  [DRY 占位电流 · 非器件数据]"
        if title is not None:
            self._result.setTitle(f"{title}{banner}")
        self._apply_axes()
        if self._cursor_lines is not None:  # clear() 移除了游标,重建
            for it in (*self._cursor_lines, self._cursor_label):
                self._result.addItem(it, ignoreBounds=True)
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
