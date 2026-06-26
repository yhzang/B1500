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
        form.addRow("协议", QLabel(self._title_of(s.get("stage", ""))))
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

    @staticmethod
    def _title_of(stage: str) -> str:
        """把协议码换成形象名给人看(协议码留后台)。"""
        try:
            from fefetlab.engine import REGISTRY
            sp = REGISTRY.get(stage)
            return sp.title if sp is not None else str(stage)
        except Exception:  # noqa: BLE001
            return str(stage)

    def _build_plot(self, preview: dict, lay) -> None:
        import math

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
        pw.setLabel("left", "栅电压", units="V")                # units= 让 pg 自动加 V/mV,不出难看的 ×0.001
        pw.setLabel("bottom", "时间", units="s")                # 自动 s/ms/µs,按数据量级走
        pw.showGrid(x=True, y=True, alpha=0.3)
        # 默认 PanMode:拖动 = 平移;滚轮 = 缩放;右键拖 = 框选放大

        ctl = QHBoxLayout()
        cb_logx = QCheckBox("X 对数轴(延迟跨度大时好用)")
        btn_reset = QPushButton("重置视图")
        btn_reset.clicked.connect(pw.autoRange)
        ctl.addWidget(cb_logx)
        ctl.addStretch(1)
        ctl.addWidget(btn_reset)
        lay.addLayout(ctl)
        lay.addWidget(pw, 1)

        pts = preview.get("gate_points", [])
        if pts:
            xs = [p[0] for p in pts]
            pw.plot(xs, [p[1] for p in pts], pen=pg.mkPen("#1565C0", width=2))
        read_lines = []
        for te in preview.get("read_events_s", []):
            ln = pg.InfiniteLine(pos=te, angle=90,
                                 pen=pg.mkPen("#D84315", width=1.5, style=Qt.PenStyle.DashLine))
            pw.addItem(ln)
            read_lines.append((ln, te))

        def _set_logx(checked):
            pw.setLogMode(x=checked)
            for ln, t in read_lines:                           # log 模式下 InfiniteLine 要换成 log10 坐标
                ln.setValue(math.log10(t) if (checked and t > 0) else t)
            pw.autoRange()

        cb_logx.toggled.connect(_set_logx)
        pos = [x for x in (xs if pts else []) if x > 0]
        if pos and max(pos) / min(pos) > 100:                  # 时间跨多个数量级 → 默认对数轴,右侧读点才看得见
            cb_logx.setChecked(True)

        note = QLabel("蓝线 = 栅电压波形(升/降沿 T_RF 是斜边,放大可见);橙虚线 = 读窗位置。"
                      "拖动平移 · 滚轮缩放 · 右键拖框选放大 · 「重置视图」复原;读点挤在一侧时勾「X 对数轴」。")
        note.setStyleSheet("color:#888;")
        note.setWordWrap(True)
        lay.addWidget(note)
