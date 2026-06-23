"""EngineWorker(+GuiCallbacks)· 在子线程跑 ProtocolEngine.run,把引擎事件 emit 成 Qt 信号。

线程铁律(设计 §2.2):所有阻塞硬件调用都在 worker 线程;**worker 绝不碰 widget**,
只 emit 信号,由主线程槽更新 UI(QueuedConnection 自动跨线程)。
取消=协作式:request_stop 只置标志,引擎在 shot/chunk 边界查 is_cancelled 干净收尾,
绝不 QThread.terminate(硬杀会让 WGFMU 会话半开 → status=-6)。

dry/live 与 backend:worker 用 `make_backend(live)` 造后端(dry→AuditBackend 无硬件),
再注入引擎门 `ProtocolEngine().run(stage, params, backend=..., callbacks=..., confirm=...)`。
params = parse_args([]) 全量默认 ∪ 表单/身份值 —— 保证 run_stage_* 需要的每个键都在。
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal, Slot


class GuiCallbacks:
    """实现 EngineCallbacks 协议:每个事件 emit 成 worker 的 Qt 信号。"""

    def __init__(self, worker: "EngineWorker") -> None:
        self._w = worker

    def on_progress(self, done: int, total: int) -> None:
        self._w.progress.emit(int(done), int(total))

    def on_shot(self, stage: str, seq: int, rows: list) -> None:
        self._w.shot.emit(str(stage), int(seq), list(rows) if rows else [])

    def on_log(self, level: str, code: str, msg: str) -> None:
        self._w.logMsg.emit(str(level), str(code), str(msg))

    def on_stage_done(self, summary: Any, run_dir: Any) -> None:
        self._w.stageDone.emit(summary, str(run_dir))

    def on_stop_gate(self, code: str, msg: str, recoverable: bool) -> None:
        self._w.stopGate.emit(str(code), str(msg), bool(recoverable))

    def on_error(self, exc: BaseException, recoverable: bool) -> None:
        self._w.errorOccurred.emit(exc, bool(recoverable))

    def is_cancelled(self) -> bool:
        return self._w._cancel


def _pattern_xy(pattern: dict) -> tuple[list, list]:
    """把 AuditBackend._patterns[name] = {'init_v', 'vectors':[(dt,v)]} 转 piecewise-linear (t,v)。"""
    init_v = float(pattern.get("init_v", 0.0))
    t: list[float] = [0.0]
    v: list[float] = [init_v]
    cur = 0.0
    for item in pattern.get("vectors", []):
        # AuditBackend 存元组 (dt, v);别的 backend 可能存 dict —— 两者都容忍
        if isinstance(item, dict):
            dt, volt = item.get("dtime_s"), item.get("voltage")
        else:
            dt, volt = item
        cur += float(dt)
        t.append(cur)
        v.append(float(volt))
    return t, v


class EngineWorker(QObject):
    """跑一次 RunRequest。moveToThread 后由 thread.started → run() 触发。"""

    progress = Signal(int, int)
    shot = Signal(str, int, object)
    logMsg = Signal(str, str, str)          # level, code, msg
    stageDone = Signal(object, object)      # StageSummary, run_dir(str)
    stopGate = Signal(str, str, bool)       # code, msg, recoverable
    errorOccurred = Signal(object, bool)    # exc, recoverable
    planReady = Signal(object)              # [{'name','x','y'}, ...] 编程波形
    finished = Signal()

    def __init__(self, req) -> None:
        super().__init__()
        self._req = req
        self._cancel = False

    @Slot()
    def request_stop(self) -> None:
        self._cancel = True

    @Slot()
    def run(self) -> None:
        # 延迟 import:保持 GUI 包加载轻,且 import 错误也能落到本方法的 except
        try:
            from fefetlab.engine import ParamView, ProtocolEngine, REGISTRY
            from fefetlab.orchestration.core import StopGate
            from fefetlab.protocols import wgfmu_fefet
            from fefetlab.protocols.smu_dc import make_backend_for
        except Exception as exc:  # noqa: BLE001
            self.errorOccurred.emit(exc, False)
            self.finished.emit()
            return

        req = self._req
        cb = GuiCallbacks(self)
        backend = None
        try:
            base = vars(wgfmu_fefet.parse_args([]))     # 全量默认,补齐所有键
            # 丢掉表单留空(None)的键,让 parse_args 默认兜底:
            # 否则清空一个有默认值的数值框会把 None 覆盖默认 → run_stage_* 里 range(None) 等崩。
            overrides = {k: v for k, v in req.params.items() if v is not None}
            params = {**base, **overrides, "live": req.live,
                      "out_root": getattr(req, "out_root", "")}
            self.logMsg.emit("INFO", "RUN_START",
                             f"stage={req.stage} live={req.live} "
                             f"device_id={params.get('device_id')}")
            # 先应用通道映射(镜像 CLI main() 顺序:configure 在 make_backend 之前)。
            # 否则 make_backend 读到的是上次/默认的模块全局,run N 会依赖 run N-1。
            # family 分流(增量6b):WGFMU 才做通道映射(镜像 CLI 顺序);SMU 旁路。backend 按 family 选。
            spec = REGISTRY.get(req.stage)
            family = spec.family if spec is not None else "WGFMU"
            if family == "WGFMU":
                try:
                    wgfmu_fefet.configure_channel_map(ParamView(params))
                except StopGate as exc:
                    cb.on_stop_gate(getattr(exc, "code", "SETUP_STOP"), str(exc), False)
                    return
            backend, _resource = make_backend_for(family, req.live)
            try:
                ProtocolEngine().run(req.stage, params, backend=backend,
                                     callbacks=cb, confirm=req.confirm)
                self._emit_waveform(backend)
            finally:
                try:
                    backend.close_session()
                except Exception:  # noqa: BLE001
                    pass
        except StopGate:
            pass  # GuiCallbacks.on_stop_gate 已 emit(engine 内部抛的)
        except Exception as exc:  # noqa: BLE001
            self.errorOccurred.emit(exc, False)
        finally:
            self.finished.emit()

    def _emit_waveform(self, backend) -> None:
        patterns = getattr(backend, "_patterns", None)
        if not patterns:
            return
        out = []
        for name, pat in patterns.items():
            t, v = _pattern_xy(pat)
            if len(t) > 1:
                out.append({"name": name, "x": t, "y": v})
        if out:
            self.planReady.emit(out)
