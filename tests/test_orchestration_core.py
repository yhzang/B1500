from __future__ import annotations

import csv
import json

import pytest

from fefetlab.orchestration import (
    ExperimentContext,
    StageSummary,
    StopGate,
    StopGatePolicy,
    make_stage_dir,
    summarize_rows,
    validate_live_request,
    write_report_code,
    write_rows_csv,
)


def test_stop_gate_policy_raises_with_stage_specific_code():
    rows = [
        {"Ig_mean_A": 1.0e-6},
        {"Ig_mean_A": -6.2e-6},
    ]
    policy = StopGatePolicy(metric="Ig_mean_A", threshold=5.0e-6, abs_value=True, threshold_label="5UA")

    with pytest.raises(StopGate) as exc:
        policy.check(rows, stage="S1")

    assert exc.value.code == "S1_STOP_IG_GT_5UA"
    assert "6.200e-06" in str(exc.value)


def test_live_request_requires_single_confirmed_stage():
    assert validate_live_request(stage="S0", live=True, confirm="S0") is None

    with pytest.raises(StopGate) as exc:
        validate_live_request(stage="ALL_DRY", live=True, confirm="ALL_DRY")
    assert exc.value.code == "SETUP_STOP_LIVE_ALL_FORBIDDEN"

    with pytest.raises(StopGate) as exc:
        validate_live_request(stage="E1", live=True, confirm="")
    assert exc.value.code == "SETUP_STOP_CONFIRM_REQUIRED_E1"


def test_export_context_groups_by_device_then_die_then_live_dryrun(tmp_path):
    # 2026-06-10 批次/器件两级归集:runs/<device>/<die>/{live,dry}/<ts>_<stage>。
    #   device = device_id(批次/自命名,可中文/空格/斜杠,经 _slug 清洗);
    #   die    = geometry[_serial](批次内具体一颗,如 L10W40_41);无 serial 退化为纯几何。
    live_ctx = ExperimentContext(
        root=tmp_path, device_id="微所pfefet2026", geometry="L10W40", serial="41", live=True
    )
    live_dir = make_stage_dir(live_ctx, "E1_RAWD", timestamp="20260610_210000")
    assert live_dir.parent == tmp_path / "runs" / "微所pfefet2026" / "L10W40_41" / "live"
    assert live_dir.name == "20260610_210000_E1_RAWD"

    # 序号缺省 → die 退化为纯几何;自命名含空格/斜杠经 _slug 清洗。
    nos_ctx = ExperimentContext(root=tmp_path, device_id="L10 W10/01", geometry="L10", live=False)
    nos_dir = make_stage_dir(nos_ctx, "ALL_DRY", timestamp="20260610_210001")
    assert nos_dir.parent == tmp_path / "runs" / "L10_W10_01" / "L10" / "dry"
    assert nos_dir.name == "20260610_210001_ALL_DRY"

    # 同批次另一颗(同 device,不同 die)自然分到平行子目录;中文 device 名原样保留。
    sib_ctx = ExperimentContext(
        root=tmp_path, device_id="微所pfefet2026", geometry="L20W10", serial="7", live=True
    )
    sib_dir = make_stage_dir(sib_ctx, "S0", timestamp="20260610_120000")
    assert sib_dir.parent == tmp_path / "runs" / "微所pfefet2026" / "L20W10_7" / "live"


def test_write_rows_and_summary_emit_same_contract(tmp_path, capsys):
    rows = [
        {"stage": "S0", "Id_mean_A": 1.0e-9, "Ig_mean_A": -2.0e-6, "extra": "kept out"},
        {"stage": "S0", "Id_mean_A": -3.0e-9, "Ig_mean_A": 1.0e-6},
    ]
    fieldnames = ["stage", "Id_mean_A", "Ig_mean_A"]
    out_csv = tmp_path / "stage" / "rows.csv"

    write_rows_csv(out_csv, rows, fieldnames)
    with out_csv.open(newline="", encoding="utf-8") as f:
        loaded = list(csv.DictReader(f))
    assert loaded[0] == {"stage": "S0", "Id_mean_A": "1e-09", "Ig_mean_A": "-2e-06"}

    summary = summarize_rows("S0", out_csv, rows, "S0_DONE")
    assert isinstance(summary, StageSummary)
    assert summary.rows == 2
    assert summary.max_abs_id_a == pytest.approx(3.0e-9)
    assert summary.max_abs_ig_a == pytest.approx(2.0e-6)

    captured = capsys.readouterr().out
    assert "REPORT_CODE: S0_DONE" in captured
    assert "STAGE_SUMMARY: stage=S0 rows=2" in captured
    assert f"OUTPUT_CSV: {out_csv}" in captured

    report_path = write_report_code(out_csv.parent, summary)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["report_code"] == "S0_DONE"
    assert payload["rows"] == 2


def test_write_report_code_uses_strict_json_for_empty_summary(tmp_path):
    summary = StageSummary(
        stage="EMPTY",
        out_csv=tmp_path / "empty.csv",
        rows=0,
        max_abs_id_a=float("nan"),
        max_abs_ig_a=float("nan"),
        report_code="EMPTY_DONE",
    )

    report_path = write_report_code(tmp_path, summary)
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    assert payload["report_code"] == "EMPTY_DONE"
    assert payload["max_abs_Id_A"] is None
    assert payload["max_abs_Ig_A"] is None
