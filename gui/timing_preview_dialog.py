"""时序预览对话框:展示 plan_preview.build_timing_preview 的结果——
摘要参数表 + 栅波形折线图(升降沿斜边可见、读窗虚线标记)。只读,关掉即走。

波形来自协议真实 build(经 AuditBackend 记录),= live 时下发的同一条。
图:白底、真实电压单位(不缩放)、拖动框选放大 / 滚轮缩放 / 重置视图 / X 可切对数。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


def _fmt_s(v) -> str:
    if v is None or v == "":
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    a = abs(v)
    if a == 0:
        return "0 s"
    if a < 1e-6:
        return f"{v * 1e9:.3g} ns"
    if a < 1e-3:
        return f"{v * 1e6:.3g} µs"
    if a < 1.0:
        return f"{v * 1e3:.3g} ms"
    return f"{v:.3g} s"


def _fmt_v(v) -> str:
    if v is None or v == "":
        return "±5V(默认)"
    if isinstance(v, str):
        return v
    return f"{v:g} V"


class TimingPreviewDialog(QDialog):
    def __init__(self, preview: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("时序预览(Plan / 预演)")
        self.resize(760, 580)
        lay = QVBoxLayout(self)
        s = preview.get("summary", {})

        box = QGroupBox("波形参数(协议真实 build,= live 时下发的同一条)")
        form = QFormLayout(box)
        form.addRow("协议", QLabel(str(s.get("stage", ""))))
        form.addRow("上升/下降沿 T_RF", QLabel(_fmt_s(s.get("t_rf_s"))))
        tw = _fmt_s(s.get("t_write_s")) if s.get("t_write_s") else "100µs(默认)"
        form.addRow("写脉冲", QLabel(f"{_fmt_v(s.get('v_write_V'))} · {tw}"))
        form.addRow("读出 Vg 点(序=读序)", QLabel(str(s.get("read_vg_V") or "—")))
        form.addRow("读窗 t_read × 点数", QLabel(f"{_fmt_s(s.get('t_read_s'))} × {s.get('n_pts')}"))
        form.addRow("读出 Vd", QLabel(_fmt_v(s.get("vd_read_V"))))
        form.addRow("延迟 / N 检查点", QLabel(str(s.get("delays_s") or "—")))
        if s.get("disturb_amp_V") is not None:
            form.addRow("扰动幅值", QLabel(f"{s.get('disturb_amp_V')} V"))
        if s.get("interval_s") is not None:
            form.addRow("脉冲间隔 Toff", QLabel(_fmt_s(s.get("interval_s"))))
        form.addRow("总时长(全部段累计)", QLabel(_fmt_s(s.get("total_shot_duration_s"))))
        fits = "一条波形装得下" if s.get("fits_one_pattern") else "超预算 → 分块跑"
        form.addRow("向量预算", QLabel(
            f"单段最大 {s.get('n_vectors_gate_max')}/{s.get('vector_budget')} · {fits} · 共 {s.get('n_executes')} 段"))
        lay.addWidget(box)

        self._build_plot(preview, lay)

        btn = QPushButton("关闭")
        btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn)
        lay.addLayout(row)

    def _build_plot(self, preview: dict, lay) -> None:
        try:
            import pyqtgraph as pg
        except Exception as exc:  # noqa: BLE001
            lay.addWidget(QLabel(f"(波形图不可用:{exc})"))
            return

        pw = pg.PlotWidget()
        self._pw = pw
        pw.setBackground("w")                                   # 白底,别黑
        for name in ("left", "bottom"):
            ax = pw.getAxis(name)
            ax.setPen("#555")
            ax.setTextPen("#555")
        pw.getAxis("left").enableAutoSIPrefix(False)            # 真实伏特,不要 ×0.001
        pw.setLabel("left", "栅电压 (V)")
        pw.setLabel("bottom", "时间 (s)")
        pw.showGrid(x=True, y=True, alpha=0.3)
        pw.getViewBox().setMouseMode(pg.ViewBox.RectMode)       # 拖动 = 框选放大

        pts = preview.get("gate_points", [])
        if pts:
            pw.plot([p[0] for p in pts], [p[1] for p in pts],
                    pen=pg.mkPen("#1565C0", width=2))
        for te in preview.get("read_events_s", []):
            pw.addItem(pg.InfiniteLine(pos=te, angle=90,
                                       pen=pg.mkPen("#D84315", width=1, style=Qt.PenStyle.DashLine)))

        ctl = QHBoxLayout()
        cb_logx = QCheckBox("X 对数轴(延迟跨度大时好用)")
        cb_logx.toggled.connect(lambda c: pw.setLogMode(x=c))
        btn_reset = QPushButton("重置视图")
        btn_reset.clicked.connect(pw.autoRange)
        ctl.addWidget(cb_logx)
        ctl.addStretch(1)
        ctl.addWidget(btn_reset)
        lay.addLayout(ctl)
        lay.addWidget(pw, 1)

        note = QLabel("蓝线 = 栅电压波形(升/降沿 T_RF 是斜边,放大可见);橙虚线 = 读窗。"
                      "拖动框选放大 · 滚轮缩放 · 「重置视图」复原。E6M 取一个 checkpoint 读段。")
        note.setStyleSheet("color:#888;")
        note.setWordWrap(True)
        lay.addWidget(note)
