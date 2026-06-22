"""MainWindow + main() · 组装三栏 + 日志 dock,接线 EngineController(共性壳)。

布局:中央 QSplitter 三栏 [协议+参数 | 运行控制 | 绘图];日志为底部 QDockWidget。
所有"动作"经 EngineController 在子线程跑,主线程只更新 widget。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("B1500 FeFET 上位机(初版)")
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

        # 中央分两页:测量(协议+参数+实时图)/ 历史浏览(增量6 RunBrowser)
        self.run_browser = RunBrowserPanel()
        central = QTabWidget()
        central.addTab(splitter, "测量")
        central.addTab(self.run_browser, "历史浏览")
        self.setCentralWidget(central)

        log_dock = QDockWidget("日志", self)
        log_dock.setWidget(self.log_panel)
        log_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, log_dock)

        self.statusBar().showMessage("就绪(dry-run 默认;本机为分析机,运行在测试机)")
        self._wire()

    def _wire(self) -> None:
        self.run_control.runClicked.connect(self._on_run)
        self.run_control.stopClicked.connect(self.controller.stop)
        self.protocol_panel.protocolSelected.connect(self._on_protocol_selected)

        c = self.controller
        c.logMsg.connect(self.log_panel.append)
        c.planReady.connect(self.plot_panel.show_waveform)
        c.shot.connect(self.plot_panel.append_shot_rows)   # 逐炮实时增量图
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
    def _on_stage_done(self, summary, run_dir) -> None:
        code = getattr(summary, "report_code", "")
        self.log_panel.append("INFO", code, f"完成 → {run_dir}")
        self.run_control.set_status(f"完成:{code}")
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
    app = QApplication(argv if argv is not None else sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
