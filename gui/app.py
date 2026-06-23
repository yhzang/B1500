"""MainWindow + main() · 组装三栏 + 日志 dock + 菜单/状态栏(共性壳)。

布局:中央 QTabWidget[测量(三栏 QSplitter)/ 历史浏览];日志为底部 QDockWidget。
顶部菜单(文件/视图/设备/帮助)+ 底部状态栏(接线指示)。窗口布局用 QSettings 持久化。
所有"动作"经 EngineController 在子线程跑,主线程只更新 widget。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
)

from . import adapters  # noqa: F401  触发 plot_dispatch 注册(FeFET 画法)
from .engine_controller import EngineController
from .log_panel import LogPanel
from .models import RunRequest
from .plot_panel import PlotPanel
from .protocol_panel import ProtocolPanel
from .run_browser_panel import RunBrowserPanel
from .run_control_panel import RunControlPanel

# 接线铁律默认(只读展示用;真实改线/跨机走后续"接线档案" SetupProfile)。容错导入。
try:
    from fefetlab.protocols.wgfmu_fefet import (
        DEFAULT_DRAIN_CH as _DRAIN,
        DEFAULT_GATE_CH as _GATE,
    )
except Exception:  # noqa: BLE001
    _GATE, _DRAIN = 202, 201
_FORBIDDEN = 302

_ORG = "fefetlab"
_APPNAME = "B1500GUI"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("B1500 FeFET 上位机")
        self.resize(1280, 800)

        self.protocol_panel = ProtocolPanel()
        self.run_control = RunControlPanel()
        self.plot_panel = PlotPanel()
        self.log_panel = LogPanel()
        self.controller = EngineController(self)

        self._last_stage: str | None = None
        self._last_live: bool = False

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.protocol_panel)
        splitter.addWidget(self.run_control)
        splitter.addWidget(self.plot_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 4)
        self._splitter = splitter

        # 中央分两页:测量(协议+参数+实时图)/ 历史浏览(增量6 RunBrowser)
        self.run_browser = RunBrowserPanel()
        central = QTabWidget()
        central.addTab(splitter, "测量")
        central.addTab(self.run_browser, "历史浏览")
        self.setCentralWidget(central)

        log_dock = QDockWidget("日志", self)
        log_dock.setObjectName("log_dock")  # restoreState 需要 objectName
        log_dock.setWidget(self.log_panel)
        log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)
        self.log_dock = log_dock

        self._build_menu()
        self._build_status_bar()
        self._wire()
        self._restore_layout()

    # ── 菜单 / 状态栏 ─────────────────────────────────────────────────────
    def _build_menu(self) -> None:
        mb = self.menuBar()

        m_file = mb.addMenu("文件(&F)")
        act_quit = QAction("退出(&Q)", self)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_view = mb.addMenu("视图(&V)")
        self.act_toggle_log = QAction("显示日志面板", self)
        self.act_toggle_log.setCheckable(True)
        self.act_toggle_log.setChecked(True)
        self.act_toggle_log.toggled.connect(self.log_dock.setVisible)
        self.log_dock.visibilityChanged.connect(self.act_toggle_log.setChecked)
        m_view.addAction(self.act_toggle_log)
        act_reset = QAction("重置布局", self)
        act_reset.triggered.connect(self._on_reset_layout)
        m_view.addAction(act_reset)

        m_dev = mb.addMenu("设备(&D)")
        act_wiring = QAction("接线档案 / 通道…", self)
        act_wiring.triggered.connect(self._on_show_wiring)
        m_dev.addAction(act_wiring)

        m_help = mb.addMenu("帮助(&H)")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._on_about)
        m_help.addAction(act_about)

    def _build_status_bar(self) -> None:
        self._wiring_label = QLabel(self._wiring_text())
        self.statusBar().addPermanentWidget(self._wiring_label)
        self.statusBar().showMessage("就绪(dry-run 默认;本机为分析机,运行在测试机)")

    def _wiring_text(self) -> str:
        return f"接线 Gate={_GATE} · Drain={_DRAIN} · CH{_FORBIDDEN} 禁用(无 RSU)"

    def _on_reset_layout(self) -> None:
        self.log_dock.setFloating(False)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_dock)
        self.log_dock.setVisible(True)

    def _on_show_wiring(self) -> None:
        QMessageBox.information(
            self, "接线档案 / 通道(只读)",
            "WGFMU 接线铁律(本机固定):\n"
            f"  Gate  = CH{_GATE}\n"
            f"  Drain = CH{_DRAIN}\n"
            f"  CH{_FORBIDDEN} 无 RSU → 禁用,不可用作 Gate/Drain\n\n"
            "SMU(DC)角色:G=4 / D=5 / S=6\n\n"
            "改接线 / 跨机器配置走「接线档案」(SetupProfile,后续里程碑)。\n"
            "live 真机连接与会话恢复属 M4(需在测试机接 B1500 验证)。")

    def _on_about(self) -> None:
        QMessageBox.about(
            self, "关于 B1500 FeFET 上位机",
            "B1500 FeFET 上位机\n\n"
            "脆弱 FeFET 单写协议 + disturb / retention / endurance 测量上位机。\n"
            "dry-run 默认(AuditBackend,无 VISA / 无 DLL);live 一段一确认。\n"
            "共性壳 + 适配层架构,可扩展到其它存储器类型(见 _agent 扩展指南)。\n\n"
            "引擎:fefetlab.engine(零 Qt) · 采集:WGFMU/SMU · 数据回流项目4。")

    # ── 布局持久化(QSettings)──────────────────────────────────────────────
    def _restore_layout(self) -> None:
        s = QSettings(_ORG, _APPNAME)
        geo = s.value("geometry")
        st = s.value("windowState")
        if geo is not None:
            self.restoreGeometry(geo)
        if st is not None:
            self.restoreState(st)

    def closeEvent(self, event) -> None:  # noqa: N802
        s = QSettings(_ORG, _APPNAME)
        s.setValue("geometry", self.saveGeometry())
        s.setValue("windowState", self.saveState())
        super().closeEvent(event)

    # ── 信号接线 ──────────────────────────────────────────────────────────
    def _wire(self) -> None:
        self.run_control.runClicked.connect(self._on_run)
        self.run_control.stopClicked.connect(self.controller.stop)
        self.protocol_panel.protocolSelected.connect(self._on_protocol_selected)

        c = self.controller
        c.logMsg.connect(self.log_panel.append)
        c.planReady.connect(self.plot_panel.show_waveform)
        c.shot.connect(self.plot_panel.append_shot_rows)   # 逐炮实时增量图
        c.shot.connect(self._on_shot)                      # 顺带更新安全指标 max|Ig|
        c.progress.connect(self.run_control.set_progress)
        c.stageDone.connect(self._on_stage_done)
        c.stopGate.connect(self._on_stop_gate)
        c.errorOccurred.connect(self._on_error)
        c.runStarted.connect(self._on_run_started)
        c.runFinished.connect(self._on_run_finished)

    def _on_protocol_selected(self, pid: str) -> None:
        from fefetlab.engine import REGISTRY

        spec = REGISTRY.get(pid)
        self.run_control.set_status(f"已选:{pid}  {spec.title if spec else ''}")

    def _on_run_started(self) -> None:
        self.run_control.set_running(True)
        self.protocol_panel.setEnabled(False)  # 运行中锁住协议树/表单,避免显示与实际跑的不一致

    def _on_run_finished(self) -> None:
        self.run_control.set_running(False)
        self.protocol_panel.setEnabled(True)

    # ── 运行 ──────────────────────────────────────────────────────────────
    def _on_run(self) -> None:
        stage = self.protocol_panel.current_protocol_id()
        if not stage:
            self.run_control.set_status("请先在左侧选择一个协议", error=True)
            return
        live = self.run_control.is_live()
        if live and not self.run_control.live_preconditions_ok():
            QMessageBox.warning(self, "live 未就绪",
                                "live 模式需勾选接线确认,并在 confirm 框手输当前 stage 码。")
            return
        if live:
            from fefetlab.engine import REGISTRY

            _spec = REGISTRY.get(stage)
            if _spec is not None and _spec.family == "SMU":
                QMessageBox.warning(self, "DC live 未实现",
                                    "DC/SMU 协议的 live 真机后端尚未接入(目前仅 dry 可用)。\n"
                                    "请切回 dry-run,或改用 WGFMU 协议做 live。")
                return
        try:
            params = self.protocol_panel.collect_params()
        except ValueError as exc:
            self.run_control.set_status(f"参数解析失败:{exc}", error=True)
            return
        params.update(self.run_control.identity())
        req = RunRequest(stage=stage, params=params, live=live,
                         confirm=self.run_control.confirm_text(),
                         out_root=self.run_control.out_root())
        if not self.controller.start(req):
            self.run_control.set_status("已有运行在进行中", error=True)
            return
        self._last_stage = stage
        self._last_live = live
        self.run_control.reset_safety()  # 新一轮清空 max|Ig|
        # 开启逐炮实时图(controller.shot 已转发 worker.shot;begin 在 shot 到达前同步执行)
        try:
            from fefetlab.engine import REGISTRY

            schema = REGISTRY[stage].csv_schema
        except Exception:  # noqa: BLE001
            schema = ""
        self.plot_panel.begin_live_plot(schema, live=live)
        self.run_control.set_status(f"运行中:{stage}（{'live' if live else 'dry'}）")
        self.log_panel.append("INFO", "SUBMIT", f"提交 {stage}")

    # ── 引擎事件 ──────────────────────────────────────────────────────────
    def _on_shot(self, stage: str, seq: int, rows) -> None:
        """每炮更新安全指标:本轮见过的 max|Ig|(从行里的 Ig_mean_A 取)。"""
        mx = 0.0
        try:
            for r in rows or ():
                v = r.get("Ig_mean_A")
                if v in (None, ""):
                    continue
                mx = max(mx, abs(float(v)))
        except Exception:  # noqa: BLE001
            return
        if mx > 0.0:
            self.run_control.update_safety(mx * 1e6)  # A → µA

    def _on_stage_done(self, summary, run_dir) -> None:
        code = getattr(summary, "report_code", "")
        self.log_panel.append("INFO", code, f"完成 → {run_dir}")
        self.run_control.set_status(f"完成:{code}")
        # 收尾把 summary 里的 max|Ig| 也并进安全指标(dry 占位/真值都覆盖)
        try:
            ig = getattr(summary, "max_abs_ig_a", None)
            if ig is not None:
                self.run_control.update_safety(abs(float(ig)) * 1e6)
        except Exception:  # noqa: BLE001
            pass
        # run_log.txt 落盘(UTF-8 无 BOM;设计 §6.4):整段日志缓冲写进本 run 目录
        try:
            Path(run_dir).joinpath("run_log.txt").write_text(
                self.log_panel.export_text(), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self.log_panel.append("WARN", "LOG", f"run_log 落盘失败:{exc}")
        try:
            from fefetlab.engine import REGISTRY

            schema = REGISTRY[self._last_stage].csv_schema if self._last_stage else ""
            out_csv = getattr(summary, "out_csv", None)
            if out_csv is not None:
                self.plot_panel.show_result(out_csv, schema, live=self._last_live)
        except Exception as exc:  # noqa: BLE001
            self.log_panel.append("WARN", "PLOT", f"结果图失败:{exc}")

    def _on_stop_gate(self, code: str, msg: str, recoverable: bool) -> None:
        self.log_panel.append("STOP", code, msg)
        self.run_control.set_status(f"停门:{code}", error=True)

    def _on_error(self, exc, recoverable: bool) -> None:
        self.log_panel.append("ERROR", type(exc).__name__, str(exc))
        self.run_control.set_status(f"错误:{exc}", error=True)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    app = QApplication(args)
    win = MainWindow()
    win.show()
    # --selftest:无人值守冒烟(离屏构造主窗口 + 进事件循环后自动退出,返回 0)。
    if "--selftest" in args:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(200, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
