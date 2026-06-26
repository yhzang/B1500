"""MainWindow + main() · 组装三栏 + 日志 dock + 菜单/状态栏(共性壳)。

布局:中央 QTabWidget[测量(三栏 QSplitter)/ 历史浏览];日志为底部 QDockWidget。
顶部菜单(文件/视图/设备/帮助)+ 底部状态栏(接线指示)。窗口布局用 QSettings 持久化。
所有"动作"经 EngineController 在子线程跑,主线程只更新 widget。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDockWidget,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
)

from . import adapters  # noqa: F401  触发 plot_dispatch 注册(FeFET 画法)
from . import presets
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

# 写/读分类(仅供写前导通提示用)。协议的权威来源是 REGISTRY(见 registry.py);
# 这里是"只读类"的显式名单——新增只读协议记得加进来。默认当写类是有意的"安全侧":
# 漏判只会对一颗器件多弹一次可关的软提示,绝不会漏掉真正的写。
_READ_ONLY_STAGES = {"S0", "S1", "DC_IDVG", "DC_IDVD"}
# 单写族(每颗只写一次,首写律):提示文案用"白费这一炮";多写族可重写,文案中性。
_SINGLE_WRITE_STAGES = {"E1S", "E6S", "E6M"}


class _PreviewWorker(QThread):
    """后台线程跑 build_timing_preview——高 N 预览会 build 全部分块,别卡主线程。"""

    done = Signal(dict)

    def __init__(self, stage: str, params: dict, parent=None) -> None:
        super().__init__(parent)
        self._stage = stage
        self._params = params

    def run(self) -> None:
        from .plan_preview import build_timing_preview
        self.done.emit(build_timing_preview(self._stage, self._params))


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
        self._last_health_status: str | None = None   # 上次读出的器件软判定(供写前提示)
        self._last_health_device: str = ""
        self._warn_no_conduction: bool = bool(
            QSettings(_ORG, _APPNAME).value("health/warn_no_conduction", True, type=bool))

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

        from .scheduler import SchedulePanel

        self.schedule_panel = SchedulePanel()
        sched_dock = QDockWidget("自动定时序列(R9)", self)
        sched_dock.setObjectName("schedule_dock")
        sched_dock.setWidget(self.schedule_panel)
        sched_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, sched_dock)
        self.schedule_dock = sched_dock

        self._presets_root = Path(__file__).resolve().parents[1]
        self._build_menu()
        self._build_toolbar()
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
        self.act_warn_cond = QAction("写前导通提示(无导通时确认)", self)
        self.act_warn_cond.setCheckable(True)
        self.act_warn_cond.setChecked(self._warn_no_conduction)
        self.act_warn_cond.toggled.connect(self._set_warn_no_conduction)
        m_dev.addAction(self.act_warn_cond)
        m_dev.addSeparator()
        act_new_recipe = QAction("新建自定义协议…", self)
        act_new_recipe.triggered.connect(self._on_new_recipe)
        m_dev.addAction(act_new_recipe)
        act_del_recipe = QAction("删除自定义协议…", self)
        act_del_recipe.triggered.connect(self._on_delete_recipe)
        m_dev.addAction(act_del_recipe)

        m_help = mb.addMenu("帮助(&H)")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._on_about)
        m_help.addAction(act_about)

    def _build_status_bar(self) -> None:
        self._wiring_label = QLabel(self._wiring_text())
        self.statusBar().addPermanentWidget(self._wiring_label)
        self.statusBar().showMessage("就绪(dry-run 默认;本机为分析机,运行在测试机)")

    # ── 命名预设(类 EasyEXPERT Favorite Setup)──────────────────────────────
    def _build_toolbar(self) -> None:
        from PySide6.QtWidgets import QToolBar

        tb = QToolBar("预设")
        tb.setObjectName("preset_toolbar")
        tb.addWidget(QLabel(" 预设: "))
        self._preset_combo = QComboBox()
        self._preset_combo.setMinimumWidth(160)
        tb.addWidget(self._preset_combo)
        for text, slot in (("加载", self._on_preset_load),
                           ("保存为…", self._on_preset_save),
                           ("删除", self._on_preset_delete)):
            act = QAction(text, self)
            act.triggered.connect(slot)
            tb.addAction(act)
        self.addToolBar(tb)
        self._refresh_presets()

    def _refresh_presets(self) -> None:
        cur = self._preset_combo.currentText()
        self._preset_combo.clear()
        names = presets.list_presets(self._presets_root)
        self._preset_combo.addItems(names)
        if cur in names:
            self._preset_combo.setCurrentText(cur)

    def _on_preset_save(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        if not self.protocol_panel.current_protocol_id():
            self.run_control.set_status("请先选协议再存预设", error=True)
            return
        name, ok = QInputDialog.getText(self, "保存预设", "预设名:")
        if ok and name.strip():
            self.save_preset_as(name.strip())

    def save_preset_as(self, name: str) -> bool:
        try:
            data = {"stage": self.protocol_panel.current_protocol_id(),
                    "params": self.protocol_panel.collect_params(),
                    "identity": self.run_control.identity()}
        except ValueError as exc:
            self.run_control.set_status(f"参数非法,未存预设:{exc}", error=True)
            return False
        presets.save_preset(self._presets_root, name, data)
        self._refresh_presets()
        self._preset_combo.setCurrentText(name)
        self.run_control.set_status(f"已存预设:{name}")
        return True

    def _on_preset_load(self) -> None:
        name = self._preset_combo.currentText().strip()
        if name:
            self.load_preset_named(name)

    def load_preset_named(self, name: str) -> bool:
        try:
            data = presets.load_preset(self._presets_root, name)
        except Exception as exc:  # noqa: BLE001
            self.run_control.set_status(f"读预设失败:{exc}", error=True)
            return False
        stage = data.get("stage")
        if stage and not self.protocol_panel.select_protocol(stage):
            self.run_control.set_status(f"预设协议 {stage} 不存在", error=True)
            return False
        self.protocol_panel.param_form.apply_values(data.get("params", {}))
        self.run_control.set_identity(data.get("identity", {}))
        self.run_control.set_status(f"已加载预设:{name}")
        return True

    def _on_preset_delete(self) -> None:
        name = self._preset_combo.currentText().strip()
        if name and presets.delete_preset(self._presets_root, name):
            self._refresh_presets()
            self.run_control.set_status(f"已删预设:{name}")

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

    def _on_new_recipe(self) -> None:
        """打开配方编辑器;保存后即时刷新协议树并选中新协议。"""
        from .recipe_editor import RecipeEditorDialog

        dlg = RecipeEditorDialog(self)
        dlg.saved.connect(self._on_recipe_saved)
        dlg.exec()

    def _on_recipe_saved(self, pid: str) -> None:
        self.protocol_panel.refresh()
        self.protocol_panel.select_protocol(pid)
        self.log_panel.append("INFO", "RECIPE", f"自定义协议已保存并注册:{pid}")
        self.run_control.set_status(f"自定义协议已加:{pid}")

    def _on_delete_recipe(self) -> None:
        """删除一条自定义协议(仅 CUSTOM,内置不可删):删盘 + 退注册 + 刷新树。"""
        from PySide6.QtWidgets import QInputDialog

        from fefetlab.protocols.declared.registry_glue import custom_recipe_ids, unregister_recipe
        from fefetlab.protocols.declared.user_store import delete_recipe

        ids = custom_recipe_ids()
        if not ids:
            QMessageBox.information(self, "删除自定义协议", "当前没有自定义协议。")
            return
        sid, ok = QInputDialog.getItem(self, "删除自定义协议", "选择要删除的:", ids, 0, False)
        if not ok or not sid:
            return
        if QMessageBox.question(self, "删除确认", f"删除自定义协议「{sid}」?") \
                != QMessageBox.StandardButton.Yes:
            return
        delete_recipe(sid)
        unregister_recipe(sid)
        self.protocol_panel.refresh()
        self.run_control.set_status(f"已删自定义协议:{sid}")
        self.log_panel.append("INFO", "RECIPE", f"已删自定义协议:{sid}")

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
        self.run_control.previewClicked.connect(self._on_preview)
        self.protocol_panel.protocolSelected.connect(self._on_protocol_selected)
        self.schedule_panel.triggerMeasurement.connect(self._on_timed_trigger)

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

    def _on_timed_trigger(self, index: int, requested_delay_s: float) -> None:
        """自动定时序列(R9)到点:跑一次当前协议(忙则跳过本点)。"""
        if self.controller.is_busy():
            self.log_panel.append("WARN", "TIMED", f"第{index + 1}点到点但上一测未完,跳过")
            return
        self.log_panel.append("INFO", "TIMED",
                              f"定时触发第{index + 1}点(目标 {requested_delay_s:g}s)")
        self._on_run()

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
        # 写前软提示:本器件上次读出没见导通时确认一次(可勾"不再提示");从不强制
        if not self._confirm_write_if_no_conduction(stage):
            self.run_control.set_status("已取消(写前确认)")
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
        self.run_control.set_status(f"运行中:{stage}（{'live' if live else '预演/plan'}）")
        self.log_panel.append("INFO", "SUBMIT", f"提交 {stage}")

    def _on_preview(self) -> None:
        """时序预览(Plan):后台 dry build 出真实波形,完成后弹对话框(沿/写/读点/delay/向量数)。"""
        stage = self.protocol_panel.current_protocol_id()
        if not stage:
            self.run_control.set_status("请先在左侧选择一个协议", error=True)
            return
        try:
            params = self.protocol_panel.collect_params()
        except ValueError as exc:
            self.run_control.set_status(f"参数解析失败:{exc}", error=True)
            return
        params.update(self.run_control.identity())
        self.run_control.set_status(f"预览生成中:{stage} …")
        self.run_control.btn_preview.setEnabled(False)
        self._preview_worker = _PreviewWorker(stage, params, self)   # 持引用,免 GC
        self._preview_worker.done.connect(self._on_preview_done)
        self._preview_worker.start()

    def _on_preview_done(self, r: dict) -> None:
        """预览线程返回:出错则提示,成功则弹时序预览对话框。"""
        self.run_control.btn_preview.setEnabled(True)
        if not r.get("ok"):
            self.run_control.set_status(f"时序预览失败:{r.get('error')}", error=True)
            return
        from .timing_preview_dialog import TimingPreviewDialog

        TimingPreviewDialog(r, self).exec()
        self.run_control.set_status(f"时序预览:{r.get('summary', {}).get('stage', '')}")

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
        # 软判定(live,只提示不拦):主读点疑似击穿/窗塌即时着色(发 on_shot 的段才有)
        try:
            from .health import assess
            v = assess(rows or [], **self.run_control.health_thresholds())
            if v["status"] in ("breakdown", "collapse"):
                self.run_control.set_health(v["label"], status=v["status"])
        except Exception:  # noqa: BLE001
            pass

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
        # 软器件判定(只提示 + 记录,从不拦):读本 run 的 CSV 看 击穿/窗塌/未导通,
        # 着色显示 + 写进 run_log(在落盘之前 append,故会被记录);阈值取面板可改值。
        try:
            out_csv = getattr(summary, "out_csv", None)
            if out_csv is not None:
                import pandas as pd

                from .health import assess
                rows = pd.read_csv(out_csv).to_dict("records")
                v = assess(rows, **self.run_control.health_thresholds())
                self.run_control.set_health(v["label"], status=v["status"])
                self._last_health_status = v["status"]
                self._last_health_device = self.run_control.identity().get("device_id", "")
                if v["status"] not in ("ok", "no_data"):
                    lvl = "STOP" if v["status"] in ("breakdown", "collapse") else "WARN"
                    self.log_panel.append(
                        lvl, f"HEALTH_{v['status'].upper()}",
                        f"{v['label']}(min|Id|={v['min_id_a']:.2e}A, max|Ig|={v['max_ig_a']:.2e}A)")
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

    # ── 写前导通软提示(从不强制;可勾"不再提示",可在 设备菜单 重新打开)──────────
    def _should_warn_no_conduction(self, stage: str) -> bool:
        """是否该弹写前确认:开关开 + 写类协议 + 本器件上次读出没见导通。"""
        if not self._warn_no_conduction:
            return False
        if stage in _READ_ONLY_STAGES:
            return False
        # 只对"读到了但 Id 偏小 = 没见导通"提示;no_data(没读到有效数据)≠没导通,
        # 不在写前再硬断言一次,交给 S1 当场横幅去判
        if self._last_health_status != "low_id":
            return False
        # 判定必须属于当前这颗器件,否则别拿别人的旧结论吓人
        return self.run_control.identity().get("device_id", "") == self._last_health_device

    def _set_warn_no_conduction(self, on: bool) -> None:
        """开/关写前导通提示(持久化 + 同步菜单勾选)。"""
        on = bool(on)
        self._warn_no_conduction = on
        QSettings(_ORG, _APPNAME).setValue("health/warn_no_conduction", on)
        act = getattr(self, "act_warn_cond", None)
        if act is not None and act.isChecked() != on:
            act.setChecked(on)

    def _write_warn_text(self, stage: str) -> str:
        """写前提示副文案:单写族强调"白费一炮",多写族中性提醒(可重写)。"""
        if stage in _SINGLE_WRITE_STAGES:
            return "单写器件每颗只写一次,写到没导通的器件会白费这一炮。"
        return "此颗上次没见导通;多写协议可重写,这里仅作提醒,确认即继续写。"

    def _confirm_write_if_no_conduction(self, stage: str) -> bool:
        """写类协议且本器件上次没见导通时,弹一次确认。返回 False=用户取消(不写)。

        勾选"本机不再提示"会持久关掉本提示(设备菜单可重新打开)。**从不强制**——
        默认就是让你确认后照写,只是别白费单写器件的那一炮。
        """
        if not self._should_warn_no_conduction(stage):
            return True
        from PySide6.QtWidgets import QCheckBox

        dev = self.run_control.identity().get("device_id", "")
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("写前确认")
        box.setText(f"器件「{dev}」上次读出没见导通(Id 偏小)。\n仍要写入 {stage} 吗?")
        box.setInformativeText(self._write_warn_text(stage))
        btn_go = box.addButton("继续写入", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        chk = QCheckBox("本机不再提示")
        box.setCheckBox(chk)
        box.exec()
        if chk.isChecked():
            self._set_warn_no_conduction(False)
        return box.clickedButton() is btn_go


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
