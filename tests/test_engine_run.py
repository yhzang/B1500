"""M1 验收 · ProtocolEngine.run 驱动 11 段 dry,逐字节对齐金标准。

证明:GUI/CLI 将调的统一执行门 `engine.run(protocol_id, params, backend=...)` 通过 `ParamView`
驱动**现有** `run_stage_*`,产出与 CLI(金标准 `tests/golden/<stage>.norm.csv`)**逐字节一致**
(抹时间戳)。即引擎收口没有改变任何协议行为——这正是 §11 M1 验收"假 EngineCallbacks 跑通
11 阶段 dry + CSV 逐字节"。
"""
from __future__ import annotations

import csv
import io
import shutil
from pathlib import Path

import pytest

from fefetlab.engine import ProtocolEngine, REGISTRY, RecordingCallbacks
from fefetlab.measurements.wgfmu.audit_backend import AuditBackend
from fefetlab.protocols.wgfmu_fefet import DELAYS_QUICK300, DRAIN_CH, GATE_CH, parse_args

GOLDEN_DIR = Path(__file__).parent / "golden"
STAGES = ["S0", "S1", "E1", "E2", "E3W", "E3A", "E4", "E5", "E6R", "E6D", "CYCLE", "MLC"]
COMMON = ["--device-id", "GOLDEN", "--geometry", "L40W10", "--seed", "20260522"]
REPS = [
    "--s0-reps", "1", "--s1-reps", "1", "--e1-reps", "1", "--e2-reps", "1",
    "--e3-reps", "1", "--e4-reps", "1", "--e5-reps", "1",
    "--e6r-reps", "1", "--e6d-reps", "1", "--cycle-count", "1", "--mlc-reps", "1",
]


def _dry_backend() -> AuditBackend:
    """复刻 make_backend 的 dry 分支:AuditBackend + open_session + FIX A/B 占位。"""
    b = AuditBackend(gate_ch=GATE_CH, drain_ch=DRAIN_CH, channels=[201, 202, 301, 302])
    b.open_session("DUMMY::WGFMU")
    b._fefet_visa_addr = "DUMMY::WGFMU"
    b._fefet_wgfmu_initialized = False
    return b


def _normalize_csv(csv_file: Path) -> str:
    with csv_file.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return ""
    ti = rows[0].index("timestamp_iso") if "timestamp_iso" in rows[0] else -1
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for i, row in enumerate(rows):
        if i > 0 and 0 <= ti < len(row):
            row = list(row)
            row[ti] = ""
        w.writerow(row)
    return buf.getvalue()


def _cleanup(out_csv: Path) -> None:
    for anc in out_csv.parents:
        if anc.name == "GOLDEN":
            shutil.rmtree(anc, ignore_errors=True)
            break


# STAGES = 有金标准的 12 段(下方逐字节回归用);ISPP 是闭环新协议,不进金标准列表
# (dry 读为占位、收敛轨迹无意义),但仍需在 REGISTRY 注册 + 被 covers 检查覆盖。
COVERED = set(STAGES) | {"ISPP", "DC_IDVG", "DC_IDVD"}  # +ISPP 闭环 +SMU DC 族(增量6b)


def test_registry_covers_all_eleven_stages():
    assert set(REGISTRY) == COVERED
    for sid in COVERED:
        assert callable(REGISTRY[sid].runner)
    for sid in set(STAGES) | {"ISPP"}:          # WGFMU 族
        assert REGISTRY[sid].family == "WGFMU"
    for sid in ("DC_IDVG", "DC_IDVD"):           # SMU 族(增量6b)
        assert REGISTRY[sid].family == "SMU"


@pytest.mark.parametrize("stage", STAGES)
def test_engine_run_byte_identical_to_golden(stage: str):
    params = vars(parse_args(["--stage", stage, *COMMON, *REPS]))
    backend = _dry_backend()
    cb = RecordingCallbacks()
    out_csv = None
    try:
        summary = ProtocolEngine().run(stage, params, backend=backend, callbacks=cb)
        out_csv = Path(summary.out_csv)
        normalized = _normalize_csv(out_csv)
    finally:
        if out_csv is not None:
            _cleanup(out_csv)

    golden = GOLDEN_DIR / f"{stage}.norm.csv"
    assert golden.exists(), f"缺金标准 {golden}(先跑 GOLDEN_REGEN=1)"
    assert normalized == golden.read_text(encoding="utf-8"), f"{stage} engine.run 输出与金标准(CLI)漂移"
    # 引擎门确实发了 on_stage_done(带 report_code)
    assert ("stage_done", summary.report_code) in cb.events


def test_engine_run_unknown_protocol_raises():
    with pytest.raises(KeyError):
        ProtocolEngine().run("NOPE", {}, backend=_dry_backend())


def test_engine_run_live_without_confirm_is_blocked():
    from fefetlab.orchestration.core import StopGate

    params = vars(parse_args(["--stage", "S0", *COMMON, *REPS, "--live"]))
    cb = RecordingCallbacks()
    with pytest.raises(StopGate):
        ProtocolEngine().run("S0", params, backend=_dry_backend(), callbacks=cb, confirm="")
    assert any(e[0] == "stop_gate" for e in cb.events)


def test_engine_run_emits_on_shot_per_shot():
    """on_shot 每炮发一次,携带该炮 rows;GUI 实时绘图/进度据此。E1 dry: 8 delays × 2 states = 16 炮。"""
    params = vars(parse_args(["--stage", "E1", *COMMON, *REPS]))
    backend = _dry_backend()
    cb = RecordingCallbacks()
    out_csv = None
    try:
        summary = ProtocolEngine().run("E1", params, backend=backend, callbacks=cb)
        out_csv = Path(summary.out_csv)
    finally:
        if out_csv is not None:
            _cleanup(out_csv)
    shots = [e for e in cb.events if e[0] == "shot"]
    assert len(shots) == len(DELAYS_QUICK300) * 2, f"E1 应发 {len(DELAYS_QUICK300) * 2} 次 on_shot,实际 {len(shots)}"
    assert all(e[1] == "E1" and e[3] > 0 for e in shots), "每炮 on_shot 应带 stage=E1 且 rows 非空"
