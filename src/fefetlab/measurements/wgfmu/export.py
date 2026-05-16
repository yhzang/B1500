"""Export helpers for WGFMU smoke workflows."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd


class WgfmuDataExporter:
    """Create run directories and persist WGFMU smoke outputs."""

    def __init__(self, base_dir: Path | str = Path("runs")):
        self.base_dir = Path(base_dir)

    def create_run_dir(self, label: str) -> Path:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        run_dir = self.base_dir / f"{timestamp}_{label}"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def build_paths(self, run_dir: Path) -> dict[str, Path]:
        return {
            "parsed": run_dir / "parsed.csv",
            "qc": run_dir / "qc.csv",
            "meta": run_dir / "meta.json",
            "export_ascii": run_dir / "setup_ascii.json",
        }

    def save_result(
        self,
        *,
        df: pd.DataFrame,
        qc_df: pd.DataFrame,
        meta: dict,
        paths: dict[str, Path],
    ) -> None:
        df.to_csv(paths["parsed"], index=False, encoding="utf-8-sig")
        qc_df.to_csv(paths["qc"], index=False, encoding="utf-8-sig")
        paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
