from __future__ import annotations


def _load_runner():
    # M1 搬家(2026-06-10)后协议逻辑在包内;直接 import 包模块。
    # (原来用 importlib.spec_from_file_location 直加载 scripts/ 脚本文件,
    #  搬家后脚本退化为薄壳、不再持有 STAGE_REGISTRY/ROOT 等符号。)
    from fefetlab.protocols import wgfmu_fefet
    return wgfmu_fefet


def test_stage_registry_is_the_single_source_for_all_dry_order():
    runner = _load_runner()

    # STAGE_REGISTRY = 协议目录(11 段确立基线 + MLC 多值 + ISPP 闭环);
    # ALL_DRY = 确立的 11 段冒烟子集(execute_count/max_vectors 锚点稳定),**刻意不含 MLC/ISPP**
    # —— 新增协议不扰动既有 ALL_DRY 基线与契约;MLC/ISPP 经 --stage + 自己的回归。
    assert list(runner.STAGE_REGISTRY) == [
        "S0", "S1", "E1", "E2", "E3W", "E3A", "E4", "E5", "E6R", "E6D", "CYCLE", "MLC", "ISPP"]
    assert runner.ALL_DRY_STAGES == (
        "S0", "S1", "E1", "E2", "E3W", "E3A", "E4", "E5", "E6R", "E6D", "CYCLE")
    assert "MLC" in runner.STAGE_REGISTRY and "MLC" not in runner.ALL_DRY_STAGES
    assert "ISPP" in runner.STAGE_REGISTRY and "ISPP" not in runner.ALL_DRY_STAGES
    assert runner.STAGE_REGISTRY["E1"].output_label == "E1_RAWD_QUICK300ms_v2"
    assert runner.STAGE_REGISTRY["CYCLE"].output_label == "CYCLE_checkpoint_endurance"
    assert runner.STAGE_REGISTRY["E6D"].output_label == "E6D_halfVdd_disturb_delay"
    assert callable(runner.STAGE_REGISTRY["E5"].runner)


def test_e6d_disturb_delay_dry_run_records_disturb_metadata(tmp_path, monkeypatch):
    runner = _load_runner()
    monkeypatch.setattr(runner, "ROOT", tmp_path)

    rc = runner.main([
        "--stage", "E6D",
        "--device-id", "L10W10_E6D",
        "--geometry", "L10W10",
        "--e6d-reps", "1",
        "--e6d-amps", "2.5",
        "--e6d-delays", "1e-6,1e-5",
    ])

    assert rc == 0
    csvs = list((tmp_path / "runs").glob("**/e6d_halfvdd_disturb_delay.csv"))
    assert len(csvs) == 1
    text = csvs[0].read_text(encoding="utf-8")
    assert "V_disturb_V" in text
    assert "delay_after_disturb_s" in text
    assert "opposite_disturb_after_ERS_-2.5V" in text
    assert "opposite_disturb_after_PGM_+2.5V" in text
    # 2 states × 2 delays × 3 Vg read points, plus header.
    assert len(text.strip().splitlines()) == 1 + 2 * 2 * 3


def test_cycle_checkpoint_dry_run_stresses_in_chunks_and_reads_only_checkpoints(tmp_path, monkeypatch):
    runner = _load_runner()
    monkeypatch.setattr(runner, "ROOT", tmp_path)

    rc = runner.main([
        "--stage", "CYCLE",
        "--device-id", "L10W10_CYCLE",
        "--geometry", "L10W10",
        "--cycle-count", "500",
        "--cycle-checkpoints", "10,100,500",
    ])

    assert rc == 0
    csvs = list((tmp_path / "runs").glob("**/cycle_checkpoint_endurance.csv"))
    assert len(csvs) == 1
    text = csvs[0].read_text(encoding="utf-8")
    assert "checkpoint_cycle=10_stress_then_read" in text
    assert "checkpoint_cycle=100_stress_then_read" in text
    assert "checkpoint_cycle=500_stress_then_read" in text
    # 3 checkpoints × 2 states × 3 Vg read points, plus header.
    assert len(text.strip().splitlines()) == 1 + 3 * 2 * 3


def test_cli_dry_run_writes_manifest_with_device_and_configurable_channels(tmp_path, monkeypatch, capsys):
    runner = _load_runner()
    monkeypatch.setattr(runner, "ROOT", tmp_path)

    rc = runner.main([
        "--stage", "S0",
        "--device-id", "L10W10_07",
        "--geometry", "L10W10",
        "--gate-ch", "301",
        "--drain-ch", "202",
        "--allowed-channels", "201,202,301",
        "--forbidden-channels", "302",
        "--s0-reps", "1",
    ])

    assert rc == 0
    out = capsys.readouterr().out
    assert "CHANNELS_OK: Gate=301, Drain=202" in out
    assert "REPORT_CODE: S0_DONE_PROCEED_TO_S1_IF_PROBES_ON_DEVICE" in out

    manifests = list((tmp_path / "runs").glob("**/manifest.yaml"))
    assert len(manifests) == 1
    text = manifests[0].read_text(encoding="utf-8")
    assert "stage: S0" in text
    assert "stage_label: S0_open_fixture_smoke" in text
    assert "device_id: L10W10_07" in text
    assert "geometry: L10W10" in text
    assert "device_family: L10" in text
    assert "gate: 301" in text
    assert "drain: 202" in text
    assert "allowed:" in text
    assert "forbidden:" in text
    assert "live: false" in text
    assert "plan_mode_equivalent: true" in text

    summaries = list((tmp_path / "runs").glob("**/summary.md"))
    assert len(summaries) == 1
    assert "# S0" in summaries[0].read_text(encoding="utf-8")
