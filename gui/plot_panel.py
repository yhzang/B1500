"""PlotPanel · 编程波形预览 + 结果图(可视化进阶) + 数据表 + 逐炮实时增量图(共性壳)。

三种绘制 + 一个表:
  * 编程波形(show_waveform):dry 跑完从 AuditBackend._patterns 取出的 gate/drain 电压意图。
  * 逐炮实时(begin_live_plot / append_shot_rows):每炮 on_shot 增量追加(环形缓冲 + 30fps 限频)。
  * 结果图(show_result):跑完按 csv_schema 查 plot_dispatch 从落盘 CSV 重读重画(权威终图)。
  * 数据表(List 视图,类 EasyEXPERT):结果 CSV 的表格,不依赖 pyqtgraph 也能看。

可视化工具条:
  * **log/线性**:X/Y 轴各自切;**按 schema 智能设默认**(fefet 的 delay 轴默认 log-X;DC 的 |Id| 默认 log-Y)。
  * **导出**:保存图片(PNG/SVG)+ 导出当前结果 CSV(回流项目4 用)。
  * Id/Ig 显隐、Id_std 误差棒、自动缩放、十字游标读坐标。结果 df 缓存,改开关即重画,不重读 CSV。

dry-run 横幅:实时/结果图标题强制标注 "DRY 占位电流(非器件数据)"。
pyqtgraph 缺失时图降级为提示文字,但数据表仍可用(本机不装、测试机才装)。
"""
from __future__ import annotations

from math import ceil
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
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
_MAX_TABLE_ROWS = 2000


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

        # 数据表(List 视图)—— 不依赖 pyqtgraph
        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        if not HAVE_PG:
            self._wave = None
            self._result = None
            self._export_status = None
            self.tabs.addTab(_missing_label(), "编程波形")
            self.tabs.addTab(_missing_label(), "结果图")
            self.tabs.addTab(self._table, "数据表")
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
        self.tabs.addTab(self._table, "数据表")

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(33)
        self._live_timer.timeout.connect(self._flush_live)

    # ── 结果图工具条(log/线性 + 导出 + 通道/误差棒/游标) ──────────────────────
    def _build_result_tab(self) -> QWidget:
        bar = QHBoxLayout()
        self._cb_logx = QCheckBox("log X")
        self._cb_logy = QCheckBox("log Y")
        self._cb_id = QCheckBox("Id"); self._cb_id.setChecked(True)
        self._cb_ig = QCheckBox("Ig")
        self._cb_err = QCheckBox("误差棒")
        self._cb_cursor = QCheckBox("十字游标")
        self._btn_auto = QPushButton("自动缩放")
        self._btn_png = QPushButton("保存图片")
        self._btn_csv = QPushButton("导出CSV")
        for w in (self._cb_logx, self._cb_logy, self._cb_id, self._cb_ig, self._cb_err, self._cb_cursor):
            bar.addWidget(w)
        bar.addWidget(self._btn_auto)
        bar.addStretch(1)
        bar.addWidget(self._btn_png)
        bar.addWidget(self._btn_csv)
        self._cb_logx.toggled.connect(self._apply_axes)
        self._cb_logy.toggled.connect(self._apply_axes)
        self._cb_id.toggled.connect(self._replot_result)
        self._cb_ig.toggled.connect(self._replot_result)
        self._cb_err.toggled.connect(self._replot_result)
        self._cb_cursor.toggled.connect(self._toggle_cursor)
        self._btn_auto.clicked.connect(lambda: self._result.enableAutoRange())
        self._btn_png.clicked.connect(self._export_image)
        self._btn_csv.clicked.connect(self._export_csv)

        self._export_status = QLabel("")
        self._export_status.setStyleSheet("color:#2E7D32;")

        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(2, 2, 2, 2)
        v.addLayout(bar)
        v.addWidget(self._result)
        v.addWidget(self._export_status)
        return box

    def _viz_options(self) -> dict:
        return {"show_id": self._cb_id.isChecked(),
                "show_ig": self._cb_ig.isChecked(),
                "error_bars": self._cb_err.isChecked()}

    def _apply_axes(self) -> None:
        if self._result is not None:
            self._result.setLogMode(x=self._cb_logx.isChecked(), y=self._cb_logy.isChecked())

    def _apply_default_axes(self, schema: str, df) -> None:
        """按 schema/数据智能设默认轴:fefet 的 delay 轴默认 log-X;DC 的 |Id| 默认 log-Y。

        用户随时可勾掉。设默认时屏蔽信号,避免 _draw_result 前重复施加。
        """
        logx, logy = False, False
        try:
            if schema == "fefet_fixedcols" and "delay_s" in getattr(df, "columns", []):
                import pandas as pd

                xs = pd.to_numeric(df["delay_s"], errors="coerce").dropna()
                pos = xs[xs > 0]
                if len(pos) > 1 and (pos.max() / max(pos.min(), 1e-30)) >= 100:
                    logx = True   # delay 跨 ≥2 个数量级 → log 更可读
            elif schema == "dc":
                logy = True       # |Id| vs Vg,电流跨多个数量级
        except Exception:  # noqa: BLE001
            pass
        for cb, val in ((self._cb_logx, logx), (self._cb_logy, logy)):
            cb.blockSignals(True)
            cb.setChecked(val)
            cb.blockSignals(False)

    def _set_export_status(self, msg: str, *, error: bool = False) -> None:
        if self._export_status is not None:
            self._export_status.setText(msg)
            self._export_status.setStyleSheet("color:#B80000;" if error else "color:#2E7D32;")

    # ── 导出(可单测:save_* 不弹对话框) ──────────────────────────────────────
    def _export_image(self) -> None:
        if self._result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存结果图", "", "PNG 图片 (*.png);;SVG 矢量图 (*.svg)")
        if path:
            self.save_result_image(path)

    def save_result_image(self, path: str) -> bool:
        """把当前结果图导出为 PNG/SVG(按后缀)。返回是否成功。"""
        if self._result is None:
            self._set_export_status("无图可保存", error=True)
            return False
        try:
            import pyqtgraph.exporters as pe

            if str(path).lower().endswith(".svg"):
                ex = pe.SVGExporter(self._result.plotItem)
            else:
                ex = pe.ImageExporter(self._result.plotItem)
            ex.export(str(path))
            self._set_export_status(f"已保存图片:{path}")
            return True
        except Exception as exc:  # noqa: BLE001
            self._set_export_status(f"保存图片失败:{exc}", error=True)
            return False

    def _export_csv(self) -> None:
        if self._last_result is None:
            self._set_export_status("无结果可导出", error=True)
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出数据 CSV(回流项目4)", "", "CSV (*.csv)")
        if path:
            self.save_result_csv(path)

    def save_result_csv(self, path: str) -> bool:
        """把当前结果 df 另存为 CSV(UTF-8 无 BOM,供回流项目4)。返回是否成功。"""
        if self._last_result is None:
            self._set_export_status("无结果可导出", error=True)
            return False
        try:
            df = self._last_result[0]
            df.to_csv(str(path), index=False, encoding="utf-8")
            self._set_export_status(f"已导出 CSV:{path}")
            return True
        except Exception as exc:  # noqa: BLE001
            self._set_export_status(f"导出失败:{exc}", error=True)
            return False

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
        self._wave.setTitle(None)          # 标题去掉:tab 已写"编程波形",不要"(最后一炮)"这种冗余
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
        # 实时也给 delay 轴默认 log-X(retention 跨数量级)
        self._cb_logx.blockSignals(True); self._cb_logx.setChecked(True); self._cb_logx.blockSignals(False)
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

    # ── 结果图(权威终图;停实时计时器)+ 数据表 ──────────────────────────────
    def show_result(self, csv_path, schema: str, *, live: bool) -> None:
        try:
            import pandas as pd
        except Exception:  # noqa: BLE001
            return
        p = Path(csv_path)
        if not p.exists():
            if self._result is not None:
                self._result.clear(); self._result.setTitle(f"找不到结果 CSV: {p}")
            return
        try:
            df = pd.read_csv(p)
        except Exception as exc:  # noqa: BLE001
            if self._result is not None:
                self._result.clear(); self._result.setTitle(f"读 CSV 失败: {exc}")
            return
        self._last_result = (df, schema, live)
        self._fill_table(df)               # 数据表(不依赖 pyqtgraph)
        if not HAVE_PG or self._result is None:
            return
        if self._live_timer is not None:
            self._live_timer.stop()
        self._live_active = False
        self._apply_default_axes(schema, df)   # 智能默认 log 轴
        self._draw_result(title=p.name)

    def _fill_table(self, df) -> None:
        cols = list(df.columns)
        n = min(len(df), _MAX_TABLE_ROWS)
        self._table.clear()
        self._table.setColumnCount(len(cols))
        self._table.setRowCount(n)
        self._table.setHorizontalHeaderLabels([str(c) for c in cols])
        for r in range(n):
            for c, col in enumerate(cols):
                self._table.setItem(r, c, QTableWidgetItem(str(df.iat[r, c])))
        self._table.resizeColumnsToContents()

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
