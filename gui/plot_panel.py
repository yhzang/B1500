"""PlotPanel · 编程波形预览 + 结果图(共性壳)。

两个标签页:
  * 编程波形:dry 跑完后由 worker 从 AuditBackend._patterns 取出的 gate/drain 向量
    (这是**真实将要下发的电压意图**,不是伪造数据),逐段 piecewise-linear 画出。
  * 结果图:按 ProtocolSpec.csv_schema 查 plot_dispatch 分派给对应适配器画。

dry-run 横幅:结果图标题强制标注 "DRY 占位电流(非器件数据)",守住"不拿占位当结果"的铁律。

pyqtgraph 缺失时整体降级为提示文字(本机不装、测试机才装)。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

from .plot_dispatch import get_plotter

try:
    import pyqtgraph as pg

    HAVE_PG = True
except Exception:  # noqa: BLE001
    HAVE_PG = False


class PlotPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tabs = QTabWidget()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.addWidget(self.tabs)

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

    # ── 公共 API ────────────────────────────────────────────────────────────
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

    def show_result(self, csv_path, schema: str, *, live: bool) -> None:
        if not HAVE_PG or self._result is None:
            return
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


def _missing_label() -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel("未安装 pyqtgraph —— 在测试机:\npip install -r requirements/gui.txt"))
    return w
