"""RunBrowserPanel · 历史 run 浏览 / 离线重画 / 多 run 叠加对比(共性壳,增量6)。

扫两级 run 目录(`runs/<device>/<die>/{live,dry}/<ts>_<stage>/`,见 orchestration/export.py),
列出历史 run;选一个 → 按其 csv_schema 离线重画;多选 → Id_mean vs delay 叠加对比。
`scan_runs` 是纯函数(无 Qt),可单测。回流项目4(复制 + 统一 UTF-8 无 BOM)留待增量6b。
"""
from __future__ import annotations

from pathlib import Path

_HELPER_CSV = ("qc", "samples", "iv_curve")  # 非主 CSV(每 run 目录可能有多个)
_OVERLAY_COLORS = ["#2659AD", "#B80000", "#1A801A", "#8000A0", "#A06000", "#0080A0"]


def _read_stage(manifest: Path) -> str:
    """从 manifest.yaml 取协议码(简单行解析,避免引 yaml 依赖)。缺失返空。"""
    try:
        for line in manifest.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if s.startswith("stage:"):
                return s.split(":", 1)[1].strip()
    except Exception:  # noqa: BLE001
        pass
    return ""


def scan_runs(root) -> list[dict]:
    """扫 root/runs 下两级布局,每个 run 目录产一条记录(纯函数,可单测)。

    返回 [{device, die, mode, run, csv, dir, manifest, stage}, ...],按 device/die/mode/run 排序。
    """
    runs_dir = Path(root) / "runs"
    if not runs_dir.is_dir():
        return []
    primary: dict[Path, Path] = {}
    for csv_path in runs_dir.glob("*/*/*/*/*.csv"):
        d = csv_path.parent
        is_helper = any(k in csv_path.name.lower() for k in _HELPER_CSV)
        if d not in primary or not is_helper:
            # 偏好非 helper CSV 作为该 run 的主 CSV
            if d not in primary or not is_helper:
                primary[d] = csv_path
    entries = []
    for d, csv_path in primary.items():
        parts = d.relative_to(runs_dir).parts
        if len(parts) != 4:
            continue
        dev, die, mode, run = parts
        entries.append({
            "device": dev, "die": die, "mode": mode, "run": run,
            "csv": str(csv_path), "dir": str(d),
            "manifest": str(d / "manifest.yaml"),
            "stage": _read_stage(d / "manifest.yaml"),
        })
    return sorted(entries, key=lambda e: (e["device"], e["die"], e["mode"], e["run"]))


# ── 以下是 Qt 壳:无 PySide6 时整模块仍可 import(scan_runs 纯函数可单测) ──────────
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QSplitter,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    _HAVE_QT = True
except Exception:  # noqa: BLE001
    _HAVE_QT = False


if _HAVE_QT:
    try:
        import pyqtgraph as pg
        _HAVE_PG = True
    except Exception:  # noqa: BLE001
        _HAVE_PG = False

    _ROLE = Qt.ItemDataRole.UserRole

    class RunBrowserPanel(QWidget):
        """历史浏览:左=run 树(device/die 分组),右=离线图;多选叠加。"""

        def __init__(self, root: str = "", parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._root = root or _default_root()

            self._root_edit = QLineEdit(self._root)
            btn_browse = QPushButton("浏览…")
            btn_refresh = QPushButton("刷新")
            btn_overlay = QPushButton("叠加所选")
            btn_export = QPushButton("导出图")
            btn_reflow = QPushButton("回流项目4…")
            btn_browse.clicked.connect(self._browse_root)
            btn_refresh.clicked.connect(self.refresh)
            btn_overlay.clicked.connect(self._overlay_selected)
            btn_export.clicked.connect(self._on_export_plot)
            btn_reflow.clicked.connect(self._on_reflow)
            top = QHBoxLayout()
            top.addWidget(QLabel("数据根:"))
            top.addWidget(self._root_edit)
            top.addWidget(btn_browse)
            top.addWidget(btn_refresh)
            top.addWidget(btn_overlay)
            top.addWidget(btn_export)
            top.addWidget(btn_reflow)

            self.tree = QTreeWidget()
            self.tree.setHeaderHidden(True)
            self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
            self.tree.currentItemChanged.connect(self._on_current)

            self._plot = pg.PlotWidget() if _HAVE_PG else QLabel("未安装 pyqtgraph")
            split = QSplitter(Qt.Orientation.Horizontal)
            left = QWidget()
            lv = QVBoxLayout(left)
            lv.setContentsMargins(0, 0, 0, 0)
            lv.addWidget(self.tree)
            split.addWidget(left)
            split.addWidget(self._plot)
            split.setStretchFactor(0, 2)
            split.setStretchFactor(1, 3)

            self._status = QLabel("")
            self._status.setStyleSheet("color:#2E7D32;")
            lay = QVBoxLayout(self)
            lay.addLayout(top)
            lay.addWidget(split)
            lay.addWidget(self._status)
            self._entries: list[dict] = []
            self.refresh()

        def refresh(self) -> None:
            self._root = self._root_edit.text().strip() or self._root
            self._entries = scan_runs(self._root)
            self.tree.clear()
            groups: dict[tuple, QTreeWidgetItem] = {}
            for e in self._entries:
                key = (e["device"], e["die"])
                grp = groups.get(key)
                if grp is None:
                    grp = QTreeWidgetItem([f"{e['device']} / {e['die']}"])
                    self.tree.addTopLevelItem(grp)
                    grp.setExpanded(True)
                    groups[key] = grp
                leaf = QTreeWidgetItem([f"[{e['mode']}] {e['run']}  ({e['stage'] or '?'})"])
                leaf.setData(0, _ROLE, e)
                grp.addChild(leaf)

        def _on_current(self, current, _prev) -> None:
            if current is None:
                return
            e = current.data(0, _ROLE)
            if e:
                self._plot_single(e)

        def _plot_single(self, e: dict) -> None:
            if not _HAVE_PG:
                return
            import pandas as pd

            from fefetlab.engine import REGISTRY

            from .plot_dispatch import get_plotter

            self._plot.clear()
            try:
                df = pd.read_csv(e["csv"])
            except Exception as exc:  # noqa: BLE001
                self._plot.setTitle(f"读 CSV 失败: {exc}")
                return
            schema = ""
            spec = REGISTRY.get(e["stage"]) if e["stage"] else None
            if spec is not None:
                schema = spec.csv_schema
            plotter = get_plotter(schema) if schema else None
            if plotter is None:
                plotter = get_plotter("fefet_fixedcols")
            if plotter is None:
                self._plot.setTitle("无可用绘图器")
                return
            live = e["mode"] == "live"
            try:
                plotter(df, self._plot, live=live, options={"show_id": True})
            except TypeError:
                plotter(df, self._plot, live=live)
            self._plot.setTitle(f"{e['device']}/{e['run']}")

        def _overlay_selected(self) -> None:
            if not _HAVE_PG:
                return
            import pandas as pd

            items = self.tree.selectedItems()
            runs = [it.data(0, _ROLE) for it in items if it.data(0, _ROLE)]
            if not runs:
                return
            self._plot.clear()
            _lg = getattr(self._plot.plotItem, "legend", None)
            if _lg is not None:
                _lg.clear()
            else:
                self._plot.addLegend(offset=(10, 10))
            self._plot.setLabel("bottom", "delay_s (s)")
            self._plot.setLabel("left", "Id_mean_A")
            for i, e in enumerate(runs):
                try:
                    df = pd.read_csv(e["csv"])
                except Exception:  # noqa: BLE001
                    continue
                if "Id_mean_A" not in df.columns:
                    continue
                y = pd.to_numeric(df["Id_mean_A"], errors="coerce").to_numpy()
                if "delay_s" in df.columns and pd.to_numeric(df["delay_s"], errors="coerce").nunique() > 1:
                    x = pd.to_numeric(df["delay_s"], errors="coerce").to_numpy()
                else:
                    x = list(range(len(y)))
                color = _OVERLAY_COLORS[i % len(_OVERLAY_COLORS)]
                self._plot.plot(x, y, pen=pg.mkPen(color=color, width=2), symbol="o",
                                symbolSize=5, symbolBrush=color, name=f"{e['device']}/{e['run']}")
            self._plot.setTitle(f"叠加 {len(runs)} 个 run")

        def _browse_root(self) -> None:
            d = QFileDialog.getExistingDirectory(self, "选择数据根目录(含 runs/)", self._root)
            if d:
                self._root_edit.setText(d)
                self.refresh()

        # ── 导出 / 回流项目4 ──────────────────────────────────────────────
        def _selected_entries(self) -> list[dict]:
            runs = [it.data(0, _ROLE) for it in self.tree.selectedItems() if it.data(0, _ROLE)]
            if not runs:
                cur = self.tree.currentItem()
                if cur is not None and cur.data(0, _ROLE):
                    runs = [cur.data(0, _ROLE)]
            return runs

        def _on_export_plot(self) -> None:
            if not _HAVE_PG:
                return
            path, _ = QFileDialog.getSaveFileName(self, "保存图片", "", "PNG 图片 (*.png);;SVG 矢量图 (*.svg)")
            if path:
                ok = self.save_plot_image(path)
                self._status.setText(f"已保存图片:{path}" if ok else "保存图片失败")

        def save_plot_image(self, path: str) -> bool:
            if not _HAVE_PG:
                return False
            try:
                import pyqtgraph.exporters as pe

                exporter = (pe.SVGExporter if str(path).lower().endswith(".svg")
                            else pe.ImageExporter)(self._plot.plotItem)
                exporter.export(str(path))
                return True
            except Exception:  # noqa: BLE001
                return False

        def _on_reflow(self) -> None:
            runs = self._selected_entries()
            if not runs:
                self._status.setText("请先选一个或多个 run")
                return
            d = QFileDialog.getExistingDirectory(self, "回流到项目4 实测数据目录", self._root)
            if not d:
                return
            n = 0
            for e in runs:
                try:
                    self.reflow_run_to(e, d)
                    n += 1
                except Exception:  # noqa: BLE001
                    pass
            self._status.setText(f"已回流 {n} 个 run → {d}(UTF-8 无 BOM)")

        def reflow_run_to(self, entry: dict, target_dir) -> Path:
            """把一个 run 的 CSV + manifest 复制到 target_dir/<run>/,统一 UTF-8 无 BOM(回流项目4)。"""
            src_dir = Path(entry["dir"])
            dst = Path(target_dir) / entry["run"]
            dst.mkdir(parents=True, exist_ok=True)
            for name in {Path(entry["csv"]).name, "manifest.yaml"}:
                src = src_dir / name
                if src.exists():
                    text = src.read_text(encoding="utf-8-sig", errors="ignore")  # 读吃掉 BOM
                    (dst / name).write_text(text, encoding="utf-8")              # 写无 BOM
            return dst


def _default_root() -> str:
    try:
        from fefetlab.protocols.wgfmu_fefet import ROOT
        return str(ROOT)
    except Exception:  # noqa: BLE001
        return ""
