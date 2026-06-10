"""M1 回归护栏 · CLI dry-run 金标准特征测试 (characterization / golden-master)。

目的:在把 1378 行 `scripts/wgfmu_next_round_minimal.py` 收口进 `fefetlab.engine` /
`fefetlab.protocols` 之前,先把**当前行为**钉成金标准,使整个引擎重构有"逐字节回归"
护栏兜底(设计文档 §11 M1 验收)。

锁定三件事:
  1. ALL_DRY 审计计数:`execute_count` / `max_vectors_seen`(AuditBackend 向量预算包络)。
  2. 每个阶段 dry-run CSV 的内容(抹掉每次都变的 `timestamp_iso` 列后逐字节一致)。
  3. 每个阶段的 `REPORT_CODE` 文本(CLI 契约)。

AuditBackend 的合成电流是固定 base/step 公式(无随机),行顺序由 `--seed` 决定,
因此固定 seed/device 下除时间戳外完全确定 —— 见 audit_backend.py。

金标准生成:`GOLDEN_REGEN=1 python -m pytest tests/test_cli_dry_golden.py -q`
会把当前输出写进 `tests/golden/`(首次建立基线 / 经确认的行为变更后刷新)。
日常 `pytest` 则严格比对,不一致即失败。

注意:这是 CLI 子进程级测试,驱动的是真实入口 `scripts/wgfmu_next_round_minimal.py`。
收口后该脚本退化为薄壳调用引擎,但 `main(argv)` 的 stdout / CSV 必须逐字节不变,
所以本测试在收口前后都应通过 —— 这正是它作为回归护栏的意义。
"""
from __future__ import annotations

import csv
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wgfmu_next_round_minimal.py"
GOLDEN_DIR = Path(__file__).parent / "golden"
REGEN = os.environ.get("GOLDEN_REGEN") == "1"

# 固定身份/种子 —— 任何一处改了金标准都要随之刷新。
COMMON = ["--device-id", "GOLDEN", "--geometry", "L40W10", "--seed", "20260522"]
# 把所有 reps 压到 1 / cycle 压到 1,金标准小而稳;脚本忽略与该段无关的 flag。
REPS = [
    "--s0-reps", "1", "--s1-reps", "1", "--e1-reps", "1", "--e2-reps", "1",
    "--e3-reps", "1", "--e4-reps", "1", "--e5-reps", "1",
    "--e6r-reps", "1", "--e6d-reps", "1", "--cycle-count", "1",
]
STAGES = ["S0", "S1", "E1", "E2", "E3W", "E3A", "E4", "E5", "E6R", "E6D", "CYCLE"]

# ALL_DRY 审计锚点 —— 用 State 记录的同一组 flag(e6r/e6d 取默认 reps=3)。
# 注意:State(2026-05-26) 记的是 96,但自那以后新增了 E6R/E6D 等段,
# 2026-06-09 实测为 169;本测试以**当前真实行为**为准,不沿用过时的 96。
ALL_DRY_FLAGS = [
    "--stage", "ALL_DRY",
    "--s0-reps", "1", "--s1-reps", "1", "--e1-reps", "1", "--e2-reps", "1",
    "--e3-reps", "1", "--e4-reps", "1", "--e5-reps", "1", "--cycle-count", "1",
]
EXPECT_EXECUTE_COUNT = 169
EXPECT_MAX_VECTORS_SEEN = 640


def _run_cli(args: list[str]) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), *args]
    # 健壮性:① stdin=DEVNULL —— 否则 pytest 的 fd 级捕获 + Windows 下大量测试同跑时,
    #   subprocess 可能拿到错乱句柄,导致 capture_output 的 stdout 变 None(本测试踩过)。
    # ② 强制 UTF-8(子进程 PYTHONUTF8=1 + 父进程 utf-8 解码)—— 保证含中文的 OUTPUT_CSV
    #   路径跨 locale 都能正确解析(CSV 文件内容本就 utf-8 落盘,不受影响)。
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _stdout_value(stdout: str, prefix: str) -> str | None:
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line.split(prefix, 1)[1].strip()
    return None


def _normalize_csv(csv_file: Path) -> str:
    """读 CSV,把 timestamp_iso 列抹空,回吐规范化文本(LF 行尾)用于稳定比对。"""
    with csv_file.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return ""
    header = rows[0]
    ti = header.index("timestamp_iso") if "timestamp_iso" in header else -1
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for i, row in enumerate(rows):
        if i > 0 and 0 <= ti < len(row):
            row = list(row)
            row[ti] = ""
        w.writerow(row)
    return buf.getvalue()


def _run_stage_capture(stage: str) -> tuple[str, str]:
    """跑一个阶段(dry),返回 (REPORT_CODE 文本, 规范化 CSV 文本)。读完即删 run 目录避免堆积。"""
    proc = _run_cli(["--stage", stage, *COMMON, *REPS])
    assert proc.returncode == 0, f"{stage} 退出码 {proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    report_code = _stdout_value(proc.stdout, "REPORT_CODE:")
    out_csv = _stdout_value(proc.stdout, "OUTPUT_CSV:")
    assert out_csv, f"{stage} 未打印 OUTPUT_CSV\nSTDOUT:\n{proc.stdout}"
    csv_path = Path(out_csv)
    try:
        normalized = _normalize_csv(csv_path)
    finally:
        run_dir = csv_path.parent
        if run_dir.exists() and run_dir.name.endswith("GOLDEN"):
            shutil.rmtree(run_dir, ignore_errors=True)
    return report_code or "", normalized


def test_all_dry_audit_counts():
    """ALL_DRY 审计计数锚点(收口后必须保持一致)。"""
    proc = _run_cli(ALL_DRY_FLAGS)
    assert proc.returncode == 0, f"ALL_DRY 退出码 {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    audit = _stdout_value(proc.stdout, "DRY_RUN_AUDIT:")
    assert audit is not None, f"未见 DRY_RUN_AUDIT 行\n{proc.stdout}"
    assert f"execute_count={EXPECT_EXECUTE_COUNT}" in audit, f"实际: {audit}"
    assert f"max_vectors_seen={EXPECT_MAX_VECTORS_SEEN}" in audit, f"实际: {audit}"


@pytest.mark.parametrize("stage", STAGES)
def test_stage_dry_golden(stage: str):
    """每段 dry-run 的 REPORT_CODE + CSV(抹时间戳)与金标准逐字节一致。"""
    report_code, normalized = _run_stage_capture(stage)

    code_golden = GOLDEN_DIR / f"{stage}.report_code.txt"
    csv_golden = GOLDEN_DIR / f"{stage}.norm.csv"

    if REGEN:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        code_golden.write_text(report_code + "\n", encoding="utf-8")
        csv_golden.write_text(normalized, encoding="utf-8")
        pytest.skip(f"GOLDEN_REGEN: 已写入 {stage} 金标准")

    assert code_golden.exists(), f"缺金标准 {code_golden},先跑 GOLDEN_REGEN=1 生成"
    assert csv_golden.exists(), f"缺金标准 {csv_golden},先跑 GOLDEN_REGEN=1 生成"
    assert report_code + "\n" == code_golden.read_text(encoding="utf-8"), f"{stage} REPORT_CODE 漂移"
    assert normalized == csv_golden.read_text(encoding="utf-8"), f"{stage} dry-run CSV 内容漂移(已抹时间戳)"
