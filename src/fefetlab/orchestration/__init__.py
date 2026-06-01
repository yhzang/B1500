"""Lightweight experiment orchestration primitives.

This package intentionally contains no instrument imports.  It is shared glue
for script-level runners (WGFMU today, SMU/DC later): live confirmation, stop
-gates, stage summaries, and stable export helpers.
"""

from .core import (
    ExperimentContext,
    StageSpec,
    StageSummary,
    StopGate,
    StopGatePolicy,
    validate_live_request,
)
from .export import make_stage_dir, summarize_rows, write_manifest_yaml, write_report_code, write_rows_csv, write_summary_md

__all__ = [
    "ExperimentContext",
    "StageSpec",
    "StageSummary",
    "StopGate",
    "StopGatePolicy",
    "validate_live_request",
    "make_stage_dir",
    "summarize_rows",
    "write_manifest_yaml",
    "write_report_code",
    "write_rows_csv",
    "write_summary_md",
]
