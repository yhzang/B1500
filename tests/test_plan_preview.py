"""Plan 时序预览:从真实 dry build 抓第一炮波形,抽出摘要 + 时间线。"""
from __future__ import annotations

import pytest

from gui.plan_preview import build_timing_preview


@pytest.mark.parametrize("stage", ["E1S", "E6S", "E6M"])
def test_preview_single_write(stage):
    r = build_timing_preview(stage)
    assert r["ok"], r.get("error")
    s = r["summary"]
    assert s["t_rf_s"] > 0                       # 上升/下降沿
    assert s["total_shot_duration_s"] > 0        # 总时长(全部段真实波形累计)
    assert s["n_vectors_gate_max"] > 0           # 抓到栅波形向量
    assert s["n_read_events"] >= 1               # 代表段至少一个读窗
    assert "v_write_V" in s                      # 写压键在(None=±5V 默认,合法)
    pts = r["gate_points"]
    assert len(pts) >= 2                          # 折线端点(含 init 起点)
    assert pts[0][0] == 0.0                       # 时间从 0 起
    ts = [p[0] for p in pts]
    assert ts == sorted(ts)                       # 时间单调不减


def test_preview_reflects_budget():
    r = build_timing_preview("E6S")
    s = r["summary"]
    assert s["vector_budget"] == 2048
    assert isinstance(s["fits_one_pattern"], bool)
    assert s["n_executes"] >= 1


def test_preview_unknown_stage_no_throw():
    r = build_timing_preview("NOPE")
    assert r["ok"] is False and "未知协议" in r["error"]


def test_preview_param_override_changes_write_v():
    base_r = build_timing_preview("E6S")
    over = build_timing_preview("E6S", {"write_v": -3.5})
    assert over["ok"]
    assert over["summary"]["v_write_V"] == -3.5
    assert over["summary"]["v_write_V"] != base_r["summary"]["v_write_V"]


@pytest.mark.parametrize("stage", ["E4", "E5", "E1", "E6R"])
def test_preview_wgfmu_base_stages_no_missing_key(stage):
    # 回归:E4/E5 等 runner 读 e1_wide_vg 等"未暴露成表单"的键;预览须铺全量默认,否则 AttributeError
    r = build_timing_preview(stage)
    assert r["ok"], r.get("error")
    assert r["summary"]["n_vectors_gate_max"] > 0
