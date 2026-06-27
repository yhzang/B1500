"""Timing-preview dialog: parameter summary + annotated gate waveform.

The waveform is the protocol's real build (captured from AuditBackend) — identical to
what a live run would send. Pulses are labelled with their voltage/width and read points
are marked, so it is obvious where reads happen and what each pulse is.
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
        return f"{v * 1e6:.3g} us"
    if a < 1.0:
        return f"{v * 1e3:.3g} ms"
    return f"{v:.3g} s"


def _fmt_v(v) -> str:
    if v is None or v == "":
        return "+/-5V (default)"
    if isinstance(v, str):
        return v
    return f"{v:g} V"


class TimingPreviewDialog(QDialog):
    def __init__(self, preview: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Timing preview (Plan)")
        self.resize(780, 580)
        lay = QVBoxLayout(self)
        s = preview.get("summary", {})

        box = QGroupBox("Waveform parameters - identical to what a live run sends")
        form = QFormLayout(box)
        form.addRow("Protocol", QLabel(self._title_of(s.get("stage", ""))))
        form.addRow("Rise / fall  T_RF", QLabel(_fmt_s(s.get("t_rf_s"))))
        tw = _fmt_s(s.get("t_write_s")) if s.get("t_write_s") else "100 us (default)"
        form.addRow("Write pulse", QLabel(f"{_fmt_v(s.get('v_write_V'))} · {tw}"))
        form.addRow("Read Vg points (= read order)", QLabel(str(s.get("read_vg_V") or "—")))
        form.addRow("Read window  t_read x N", QLabel(f"{_fmt_s(s.get('t_read_s'))} x {s.get('n_pts')}"))
        form.addRow("Read Vd", QLabel(_fmt_v(s.get("vd_read_V"))))
        form.addRow("Delays / N checkpoints", QLabel(str(s.get("delays_s") or "—")))
        if s.get("disturb_amp_V") is not None:
            form.addRow("Disturb amplitude", QLabel(f"{s.get('disturb_amp_V')} V"))
        if s.get("interval_s") is not None:
            form.addRow("Pulse interval  Toff", QLabel(_fmt_s(s.get("interval_s"))))
        form.addRow("Total duration (all segments)", QLabel(_fmt_s(s.get("total_shot_duration_s"))))
        fits = "fits one pattern" if s.get("fits_one_pattern") else "over budget -> chunked"
        form.addRow("Vector budget", QLabel(
            f"max {s.get('n_vectors_gate_max')}/{s.get('vector_budget')} per segment · {fits} · {s.get('n_executes')} segments"))
        lay.addWidget(box)

        self._build_plot(preview, lay)

        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn)
        lay.addLayout(row)

    @staticmethod
    def _title_of(stage: str) -> str:
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
            lay.addWidget(QLabel(f"(plot unavailable: {exc})"))
            return

        pw = pg.PlotWidget()
        self._pw = pw
        pw.setBackground("w")
        for name in ("left", "bottom"):
            ax = pw.getAxis(name)
            ax.setPen("#555")
            ax.setTextPen("#555")
        pw.setLabel("left", "Gate", units="V")
        pw.setLabel("bottom", "Time", units="s")
        pw.showGrid(x=True, y=True, alpha=0.3)

        ctl = QHBoxLayout()
        cb_logx = QCheckBox("X log axis (good for wide delay spans)")
        btn_reset = QPushButton("Reset view")
        btn_reset.clicked.connect(pw.autoRange)
        ctl.addWidget(cb_logx)
        ctl.addStretch(1)
        ctl.addWidget(btn_reset)
        lay.addLayout(ctl)
        lay.addWidget(pw, 1)

        xitems = []   # (item, data_x) so labels/lines can move when X goes log

        pts = preview.get("gate_points", [])
        xs = [p[0] for p in pts]
        if pts:
            pw.plot(xs, [p[1] for p in pts], pen=pg.mkPen("#1565C0", width=2))

        def _label(t, v, text, color, anchor):
            ti = pg.TextItem(text, color=color, anchor=anchor)
            ti.setPos(t, v)
            pw.addItem(ti)
            xitems.append((ti, t))

        for p in preview.get("pulses", []):                 # write / disturb pulses
            _label(p["t"], p["v"], f"{p['v']:g} V\n{_fmt_s(p['width'])}", "#0C447C", (0.5, 1.1))
        for r in preview.get("reads", []):                  # read plateaus
            _label(r["t"], r["v"], f"READ {r['v']:g} V", "#993C1D", (0.5, -0.1))
        for te in preview.get("read_events_s", []):         # vertical marker at every read
            ln = pg.InfiniteLine(pos=te, angle=90,
                                 pen=pg.mkPen("#D84315", width=1.2, style=Qt.PenStyle.DashLine))
            pw.addItem(ln)
            xitems.append((ln, te))

        def _set_logx(checked):
            pw.setLogMode(x=checked)
            for it, t in xitems:
                x = math.log10(t) if (checked and t > 0) else t
                if isinstance(it, pg.InfiniteLine):
                    it.setValue(x)
                else:
                    it.setPos(x, it.pos().y())
            pw.autoRange()

        cb_logx.toggled.connect(_set_logx)
        pos = [x for x in xs if x > 0]
        if pos and max(pos) / min(pos) > 100:               # spans decades -> default log so reads spread out
            cb_logx.setChecked(True)

        note = QLabel("Blue = gate-voltage waveform (T_RF rise/fall = sloped edges, zoom to see). "
                      "Blue labels = pulse V / width; red labels + dashed lines = read points. "
                      "Drag to pan · wheel to zoom · right-drag to box-zoom · Reset view to fit.")
        note.setStyleSheet("color:#888;")
        note.setWordWrap(True)
        lay.addWidget(note)
