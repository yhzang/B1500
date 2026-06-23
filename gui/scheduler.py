"""长延迟自动定时序列(R9)· 写后秒-分钟级 delay 自动计时 + 触发,记 requested vs actual。

依据:项目4 02_Plan「定时功能」+ 分析 R9。µs 级 intra-sequence delay 已编进硬件波形;
本件解决**秒-分钟级长 delay 不用手动掐表**:给一组相对 t0 的 delay(秒),GUI 每秒查"到点没",
到点就触发当前协议测一次,并记 requested_delay_s vs 实际触发墙钟 actual_delay_s。

DelaySchedule 是纯逻辑(零 Qt,clock 可注入)→ 可单测;SchedulePanel 是 Qt 壳。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class DelaySchedule:
    """一组相对 t0 的延迟点(秒)的调度。墙钟由外部传入(可注入假钟,便于测试)。"""

    delays_s: list
    t0: float
    _fired: dict = field(default_factory=dict)   # index -> 实际触发墙钟

    def fire_time(self, i: int) -> float:
        return self.t0 + float(self.delays_s[i])

    def next_pending(self):
        for i in range(len(self.delays_s)):
            if i not in self._fired:
                return i
        return None

    def due(self, now: float):
        i = self.next_pending()
        if i is not None and now >= self.fire_time(i):
            return i
        return None

    def seconds_to_next(self, now: float):
        i = self.next_pending()
        return None if i is None else max(0.0, self.fire_time(i) - now)

    def mark_fired(self, i: int, now: float) -> dict:
        self._fired[i] = now
        return {"index": i, "requested_delay_s": float(self.delays_s[i]),
                "actual_delay_s": now - self.t0}

    def done(self) -> bool:
        return self.next_pending() is None

    def records(self) -> list:
        return [{"index": i, "requested_delay_s": float(self.delays_s[i]),
                 "actual_delay_s": self._fired[i] - self.t0}
                for i in sorted(self._fired)]


def parse_delays(text: str) -> list:
    """解析逗号分隔的延迟(秒)。非法/非正/空 抛 ValueError。"""
    out = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        v = float(part)
        if v <= 0:
            raise ValueError(f"延迟须为正秒数:{part}")
        out.append(v)
    if not out:
        raise ValueError("延迟列表不能为空")
    return out


# ── Qt 壳(无 PySide6 时纯逻辑仍可 import 单测)──────────────────────────────
try:
    from PySide6.QtCore import QTimer, Signal
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    _HAVE_QT = True
except Exception:  # noqa: BLE001
    _HAVE_QT = False


if _HAVE_QT:

    class SchedulePanel(QWidget):
        """自动定时序列:输入 delay 列表 → 开始 → 每秒倒计时 → 到点 emit triggerMeasurement。

        triggerMeasurement(index, requested_delay_s):上层(MainWindow)据此跑一次当前协议。
        clock 可注入(默认 time.monotonic),便于离线测试 _tick。
        """

        triggerMeasurement = Signal(int, float)
        finished = Signal()

        def __init__(self, parent=None, clock=None) -> None:
            super().__init__(parent)
            self._clock = clock or time.monotonic
            self._sched: DelaySchedule | None = None

            self._delays_edit = QLineEdit("10, 30, 60, 120, 300")
            self._delays_edit.setPlaceholderText("逗号分隔延迟秒数,如 10,30,60,120,300")
            self._btn = QPushButton("开始定时序列")
            self._btn.setCheckable(True)
            self._btn.toggled.connect(self._on_toggle)
            self._countdown = QLabel("未开始(写后从点开始那刻计时)")

            top = QHBoxLayout()
            top.addWidget(QLabel("写后延迟(s):"))
            top.addWidget(self._delays_edit)
            top.addWidget(self._btn)

            self._table = QTableWidget(0, 3)
            self._table.setHorizontalHeaderLabels(["#", "requested (s)", "actual (s)"])

            lay = QVBoxLayout(self)
            lay.addLayout(top)
            lay.addWidget(self._countdown)
            lay.addWidget(self._table)

            self._timer = QTimer(self)
            self._timer.setInterval(1000)
            self._timer.timeout.connect(self._tick)

        # 公共 API(可测)
        def start(self, delays_s=None) -> bool:
            try:
                delays = (list(delays_s) if delays_s is not None
                          else parse_delays(self._delays_edit.text()))
            except ValueError as exc:
                self._countdown.setText(f"延迟非法:{exc}")
                return False
            self._sched = DelaySchedule(delays, self._clock())
            self._table.setRowCount(len(delays))
            for i, d in enumerate(delays):
                self._table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                self._table.setItem(i, 1, QTableWidgetItem(f"{d:g}"))
                self._table.setItem(i, 2, QTableWidgetItem("—"))
            self._timer.start()
            self._tick()
            return True

        def stop(self) -> None:
            self._timer.stop()
            self._sched = None
            self._countdown.setText("已停止")

        def is_running(self) -> bool:
            return self._sched is not None and not self._sched.done()

        def _on_toggle(self, on: bool) -> None:
            if on:
                ok = self.start()
                self._btn.setText("停止定时序列" if ok else "开始定时序列")
                if not ok:
                    self._btn.setChecked(False)
            else:
                self.stop()
                self._btn.setText("开始定时序列")

        def _tick(self) -> None:
            if self._sched is None:
                return
            now = self._clock()
            due = self._sched.due(now)
            if due is not None:
                rec = self._sched.mark_fired(due, now)
                self._table.setItem(due, 2, QTableWidgetItem(f"{rec['actual_delay_s']:.1f}"))
                self.triggerMeasurement.emit(due, rec["requested_delay_s"])
                if self._sched.done():
                    self._timer.stop()
                    self._countdown.setText("定时序列完成")
                    self._btn.setChecked(False)
                    self.finished.emit()
                    return
            s = self._sched.seconds_to_next(now)
            i = self._sched.next_pending()
            if s is not None and i is not None:
                self._countdown.setText(
                    f"下一测(第 {i + 1}/{len(self._sched.delays_s)} 点)还有 {s:.0f}s")
