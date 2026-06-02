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


def test_export_context_separates_live_and_dryrun_under_runs(tmp_path):
    live_ctx = ExperimentContext(root=tmp_path, device_id="L10 W10/01", geometry="L10", live=True)
    live_dir = make_stage_dir(live_ctx, "E1_RAWD", timestamp="20260526_210000")
    assert live_dir.parent == tmp_path / "runs" / "live"
    assert live_dir.name == "20260526_210000_E1_RAWD_L10_W10_01"

    dry_ctx = ExperimentContext(root=tmp_path, device_id="DRY", geometry="NA", live=False)
    dry_dir = make_stage_dir(dry_ctx, "ALL_DRY", timestamp="20260526_210001")
    assert dry_dir.parent == tmp_path / "runs" / "dry"
    assert dry_dir.name == "20260526_210001_ALL_DRY_DRY"


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
