"""EngineCallbacks · 引擎向上层(GUI / CLI / 测试)发射的唯一事件契约。

设计文档 §3.6(收敛三份草稿签名)。引擎层零 Qt:GUI 端实现一个把每个方法 `emit` 成
Qt 信号的 `GuiCallbacks`;CLI 端实现打印 `SHOT_OK/REPORT_CODE` 的 `CliCallbacks`;
测试用 `NullCallbacks` 或 `RecordingCallbacks`。

当前 M1 阶段:引擎在 `engine.run` 这一层能可靠发 `on_stage_done` / `on_stop_gate` /
`on_error`(都在门内捕获);`on_progress` / `on_shot` 需把回调线接进 `run_stage_*` 的 shot
循环(D1,M1 后续一步,届时 runner 改为 `(backend, view, *, callbacks=None)`)。
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EngineCallbacks(Protocol):
    """上层只需实现这套方法即可接收引擎事件;全部可选语义,实现可空操作。"""

    def on_progress(self, done: int, total: int) -> None: ...
    def on_shot(self, stage: str, seq: int, rows: list) -> None: ...           # 每个 run_*_shot 返回后
    def on_log(self, level: str, code: str, msg: str) -> None: ...
    def on_stage_done(self, summary: Any, run_dir: Any) -> None: ...
    def on_stop_gate(self, code: str, msg: str, recoverable: bool) -> None: ...
    def on_error(self, exc: BaseException, recoverable: bool) -> None: ...
    def is_cancelled(self) -> bool: ...


class NullCallbacks:
    """全空实现。引擎默认用它(CLI 现仍靠 runner 内的 print 出 SHOT_OK/REPORT_CODE)。"""

    def on_progress(self, done: int, total: int) -> None:
        pass

    def on_shot(self, stage: str, seq: int, rows: list) -> None:
        pass

    def on_log(self, level: str, code: str, msg: str) -> None:
        pass

    def on_stage_done(self, summary: Any, run_dir: Any) -> None:
        pass

    def on_stop_gate(self, code: str, msg: str, recoverable: bool) -> None:
        pass

    def on_error(self, exc: BaseException, recoverable: bool) -> None:
        pass

    def is_cancelled(self) -> bool:
        return False


class RecordingCallbacks(NullCallbacks):
    """测试用:把收到的事件记进列表,断言引擎确实发了 on_stage_done / on_stop_gate 等。"""

    def __init__(self) -> None:
        self.events: list[tuple] = []

    def on_stage_done(self, summary: Any, run_dir: Any) -> None:
        self.events.append(("stage_done", getattr(summary, "report_code", None)))

    def on_stop_gate(self, code: str, msg: str, recoverable: bool) -> None:
        self.events.append(("stop_gate", code, recoverable))

    def on_error(self, exc: BaseException, recoverable: bool) -> None:
        self.events.append(("error", type(exc).__name__, recoverable))
