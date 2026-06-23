"""RunControlPanel · 器件身份 + dry/live + 运行/停止 + 预检/安全 + 状态(共性壳)。

身份字段(device_id/geometry/serial/device_type/operator)**不在协议参数表单里**
(REGISTRY.params 刻意不含身份,见 registry.py);它们是运行头元数据,放这里,
worker 会并进 params 交给 run_stage_*/_build_manifest。

安全 UI:dry 默认;切 live 时控制区变淡红 + 必须勾选接线确认 + 手输 stage 码
(confirm 唯一语义最终由引擎 validate_live_request 兜底:confirm 必须 == stage)。
预检/安全组:展示接线(Gate/Drain/CH302)+ 本轮 max|Ig|(由 on_shot 喂入)。
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

# 接线默认(只读展示;真实改线/跨机走接线档案)。容错导入。
try:
    from fefetlab.protocols.wgfmu_fefet import (
        DEFAULT_DRAIN_CH as _DRAIN,
        DEFAULT_GATE_CH as _GATE,
    )
except Exception:  # noqa: BLE001
    _GATE, _DRAIN = 202, 201

# 身份字段 UI 默认(与 wgfmu_fefet.parse_args 默认一致,仅作初值)
_ID_DEFAULTS = {
    "device_id": "L40W10_01",
    "geometry": "L40W10",
    "serial": "",
    "device_type": "",
    "operator": "",
}


class RunControlPanel(QWidget):
    """中栏:身份 + 模式 + 预检/安全 + 运行控制。"""

    runClicked = Signal()
    stopClicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._max_ig_uA = 0.0

        # ── 器件身份 ──
        id_box = QGroupBox("器件 / 运行身份")
        id_form = QFormLayout(id_box)
        self._id_edits: dict[str, QLineEdit] = {}
        labels = {
            "device_id": "device_id(批次/自命名)",
            "geometry": "geometry(几何)",
            "serial": "serial(序号,可空)",
            "device_type": "device_type(pFeFET/nFeFET,可空)",
            "operator": "operator(测试人,可空)",
        }
        for key, lab in labels.items():
            le = QLineEdit(_ID_DEFAULTS[key])
            self._id_edits[key] = le
            id_form.addRow(QLabel(lab), le)

        # 输出根目录(默认空 = 仓库 runs/;可浏览改到别的盘)
        self._out_root = QLineEdit()
        self._out_root.setPlaceholderText("(默认:仓库 runs/)")
        self._btn_browse = QPushButton("浏览…")
        self._btn_browse.clicked.connect(self._browse_out_root)
        out_row = QHBoxLayout()
        out_row.addWidget(self._out_root)
        out_row.addWidget(self._btn_browse)
        id_form.addRow(QLabel("输出根目录"), out_row)

        # ── 模式 ──
        self._mode_box = QGroupBox("模式")
        mode_lay = QVBoxLayout(self._mode_box)
        self.rb_dry = QRadioButton("dry-run(默认,无 VISA / 无 DLL / 占位电流)")
        self.rb_live = QRadioButton("live(真机,一段一确认)")
        self.rb_dry.setChecked(True)
        self.rb_dry.toggled.connect(self._on_mode_toggled)
        mode_lay.addWidget(self.rb_dry)
        mode_lay.addWidget(self.rb_live)

        self._live_box = QGroupBox("live 确认(仅 live 时需要)")
        live_form = QFormLayout(self._live_box)
        self.chk_wiring = QCheckBox("我已确认探针位置与接线(Gate=202 / Drain=201)")
        self.ed_confirm = QLineEdit()
        self.ed_confirm.setPlaceholderText("手输当前 stage 码,如 E1")
        live_form.addRow(self.chk_wiring)
        live_form.addRow(QLabel("confirm ="), self.ed_confirm)
        self._live_box.setVisible(False)

        # ── 预检 / 安全 ──
        self._safety_box = QGroupBox("预检 / 安全")
        sb_form = QFormLayout(self._safety_box)
        self._pf_errx = QLabel("ERRX 预检:dry 模拟通过")
        self._pf_chan = QLabel(f"通道:Gate={_GATE} / Drain={_DRAIN}")
        self._pf_302 = QLabel("CH302:禁用(无 RSU)")
        for _w in (self._pf_errx, self._pf_chan, self._pf_302):
            _w.setStyleSheet("color:#2E7D32;")
        self._safety = QLabel("本轮 max|Ig|: -- µA")
        sb_form.addRow(self._pf_errx)
        sb_form.addRow(self._pf_chan)
        sb_form.addRow(self._pf_302)
        sb_form.addRow(self._safety)
        # ── 软器件判定(只提示 + 记录,从不拦;阈值默认可改)──
        self._cond_uA = QDoubleSpinBox()
        self._cond_uA.setRange(0.0, 1000.0)
        self._cond_uA.setDecimals(2)
        self._cond_uA.setValue(5.0)
        self._cond_uA.setSuffix(" µA")
        self._cond_uA.setToolTip("主读点 |Id| ≥ 此值才算导通(S1 体检参考);只提示不拦")
        self._collapse_k = QDoubleSpinBox()
        self._collapse_k.setRange(0.0, 100.0)
        self._collapse_k.setDecimals(1)
        self._collapse_k.setValue(3.0)
        self._collapse_k.setSuffix(" ×σ")
        self._collapse_k.setToolTip("|Id| < k×Id_std(信号没过噪声)且 Ig 健康 → 疑似窗塌;只提示不拦")
        sb_form.addRow(QLabel("导通阈 |Id|≥"), self._cond_uA)
        sb_form.addRow(QLabel("窗塌阈 |Id|<"), self._collapse_k)
        self._health = QLabel("器件判定:—")
        sb_form.addRow(self._health)

        # ── 运行控制 ──
        self.btn_run = QPushButton("▶ 运行")
        self.btn_stop = QPushButton("■ 停止")
        self.btn_stop.setEnabled(False)
        self.btn_run.clicked.connect(self.runClicked)
        self.btn_stop.clicked.connect(self.stopClicked)
        btn_lay = QHBoxLayout()
        btn_lay.addWidget(self.btn_run)
        btn_lay.addWidget(self.btn_stop)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # 初版:不确定总数时显示忙碌动画
        self.progress.setVisible(False)
        self.status = QLabel("就绪")
        self.status.setWordWrap(True)

        lay = QVBoxLayout(self)
        lay.addWidget(id_box)
        lay.addWidget(self._mode_box)
        lay.addWidget(self._live_box)
        lay.addWidget(self._safety_box)
        lay.addLayout(btn_lay)
        lay.addWidget(self.progress)
        lay.addWidget(self.status)
        lay.addStretch(1)

    # ── 公共 API ────────────────────────────────────────────────────────────
    def identity(self) -> dict[str, str]:
        return {k: e.text().strip() for k, e in self._id_edits.items()}

    def set_identity(self, identity: dict) -> None:
        """从预设回填器件身份字段。"""
        for k, e in self._id_edits.items():
            if identity and k in identity and identity[k] is not None:
                e.setText(str(identity[k]))

    def out_root(self) -> str:
        """输出根目录(空 = 用仓库默认 ROOT)。"""
        return self._out_root.text().strip()

    def is_live(self) -> bool:
        return self.rb_live.isChecked()

    def confirm_text(self) -> str:
        return self.ed_confirm.text().strip()

    def live_preconditions_ok(self) -> bool:
        """live 提交的 UI 双保险(引擎仍会兜底)。dry 永远 True。"""
        if not self.is_live():
            return True
        return self.chk_wiring.isChecked() and self.confirm_text() != ""

    def set_running(self, running: bool) -> None:
        self.btn_run.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.progress.setVisible(running)
        if running:
            self.progress.setRange(0, 0)  # 每次开跑先回到 busy(不确定总数)
        for e in self._id_edits.values():
            e.setEnabled(not running)
        self._mode_box.setEnabled(not running)
        self._live_box.setEnabled(not running)

    def set_progress(self, done: int, total: int) -> None:
        """引擎 on_progress 到达时切到确定进度;total<=0 维持 busy 动画。

        注:当前 run_stage_* 尚未发 on_progress(M1 余项),所以暂时只会维持 busy;
        本槽接好后,等 runner 接入 on_shot/on_progress 即自动生效。
        """
        if total and total > 0:
            self.progress.setRange(0, int(total))
            self.progress.setValue(int(done))
        else:
            self.progress.setRange(0, 0)

    def set_status(self, text: str, *, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setStyleSheet("color:#B80000;" if error else "")

    def reset_safety(self) -> None:
        """新一轮运行前清空 max|Ig| 指标 + 器件判定。"""
        self._max_ig_uA = 0.0
        self._safety.setText("本轮 max|Ig|: -- µA")
        self._safety.setStyleSheet("")
        self._health.setText("器件判定:—")
        self._health.setStyleSheet("")

    def health_thresholds(self) -> dict:
        """软判定阈值(默认 5µA / 3×σ,用户可改):导通 |Id|≥µA、窗塌 |Id|<k×Id_std。"""
        return {"conduction_uA": float(self._cond_uA.value()),
                "collapse_k": float(self._collapse_k.value())}

    def set_health(self, label: str, *, status: str = "ok") -> None:
        """显示器件软判定(只提示,从不拦)。status 决定着色。"""
        self._health.setText(f"器件判定:{label}")
        if status in ("collapse", "breakdown"):
            self._health.setStyleSheet("color:#B80000;font-weight:bold;")
        elif status == "low_id":
            self._health.setStyleSheet("color:#B8860B;font-weight:bold;")
        else:
            self._health.setStyleSheet("color:#2E7D32;")

    def update_safety(self, ig_uA: float) -> None:
        """收到更高的 |Ig|(µA)时更新指标 + 着色(经验:≥20µA 偏高,标红)。"""
        if ig_uA <= self._max_ig_uA:
            return
        self._max_ig_uA = ig_uA
        self._safety.setText(f"本轮 max|Ig|: {ig_uA:.3g} µA")
        self._safety.setStyleSheet(
            "color:#B80000;font-weight:bold;" if ig_uA >= 20 else "color:#2E7D32;")

    # ── 内部 ────────────────────────────────────────────────────────────────
    def _browse_out_root(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        d = QFileDialog.getExistingDirectory(self, "选择输出根目录")
        if d:
            self._out_root.setText(d)

    def _on_mode_toggled(self, _checked: bool) -> None:
        live = self.is_live()
        self._live_box.setVisible(live)
        self._pf_errx.setText("ERRX 预检:live 由引擎执行(不发 *CLS/*RST)" if live
                              else "ERRX 预检:dry 模拟通过")
        self._pf_errx.setStyleSheet("color:#B8860B;" if live else "color:#2E7D32;")
        # live 时整条控制区淡红底,提醒
        self.setStyleSheet("RunControlPanel{background:#FFF0F0;}" if live else "")
