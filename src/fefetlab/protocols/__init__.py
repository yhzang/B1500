"""fefetlab 协议层:具体测量协议的可执行实现(runner)。

M1 搬家(2026-06-10):原 `scripts/wgfmu_next_round_minimal.py` 的全部协议逻辑
(常量 / `run_*_shot` / `run_stage_*` / `_build_read_phase` /
`_configure_and_run_phase` / `_summarize_windows` / `FIELDNAMES` /
`STAGE_REGISTRY` / `parse_args` / `main`)整体搬入 `wgfmu_fefet.py`,
脚本退化为薄壳。引擎 / GUI / CLI 共用此处的 `STAGE_REGISTRY` 与 `main`。
"""
from . import wgfmu_fefet

__all__ = ["wgfmu_fefet"]
