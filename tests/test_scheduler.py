"""R9 自动定时序列:纯调度逻辑 + SchedulePanel(注入假钟)到点触发。"""
from __future__ import annotations

import pytest


def test_delay_schedule_pure():
    from gui.scheduler import DelaySchedule

    s = DelaySchedule([10, 30], t0=1000.0)
    assert s.due(1005) is None
    assert abs(s.seconds_to_next(1005) - 5) < 1e-9
    assert s.due(1011) == 0
    rec = s.mark_fired(0, 1011)
    assert rec["requested_delay_s"] == 10 and abs(rec["actual_delay_s"] - 11) < 1e-9
    assert s.due(1011) is None            # 0 已触发,下一个是 1(30s,未到)
    assert s.due(1031) == 1
    s.mark_fired(1, 1031)
    assert s.done() is True
    assert len(s.records()) == 2


def test_parse_delays():
    from gui.scheduler import parse_delays

    assert parse_delays("10, 30, 60") == [10.0, 30.0, 60.0]
    with pytest.raises(ValueError):
        parse_delays("")
    with pytest.raises(ValueError):
        parse_delays("10, -5")


def test_schedule_panel_triggers_on_time(qapp):
    pytest.importorskip("PySide6")
    from gui.scheduler import SchedulePanel

    clock = {"t": 1000.0}
    panel = SchedulePanel(clock=lambda: clock["t"])
    fired = []
    panel.triggerMeasurement.connect(lambda i, d: fired.append((i, d)))

    assert panel.start([10, 30]) is True
    clock["t"] = 1005; panel._tick()          # 还没到点
    assert fired == []
    clock["t"] = 1011; panel._tick()          # 第 0 点(10s)触发
    assert fired == [(0, 10.0)]
    clock["t"] = 1031; panel._tick()          # 第 1 点(30s)触发,序列完成
    assert fired == [(0, 10.0), (1, 30.0)]
    assert panel.is_running() is False
