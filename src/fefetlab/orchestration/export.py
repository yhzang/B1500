from __future__ import annotations

import csv
import datetime as _dt
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .core import ExperimentContext, StageSummary


def _now_tag() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def make_stage_dir(ctx: ExperimentContext, stage: str, timestamp: str | None = None) -> Path:
    """Return the output directory for one stage.

    Dry-run and live results deliberately live side-by-side under ``runs/`` so
    each simulation/measurement purpose can be compared by date without mixing
    hardware-free audits with real instrument outputs.
    """

    base = ctx.root / "runs" / ("live" if ctx.live else "dry")
    return base / f"{timestamp or _now_tag()}_{stage}_{ctx.device_slug}"


def write_rows_csv(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    """Write stage rows using a fixed schema, ignoring extra keys."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def _max_abs(rows: list[Mapping[str, Any]], key: str) -> float:
    vals: list[float] = []
    for row in rows:
        raw = row.get(key, float("nan"))
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isnan(value):
            vals.append(abs(value))
    return max(vals) if vals else float("nan")


def summarize_rows(stage: str, out_csv: Path, rows: list[Mapping[str, Any]], code: str) -> StageSummary:
    """Print and return the stable WGFMU-style stage summary contract."""

    max_id = _max_abs(rows, "Id_mean_A")
    max_ig = _max_abs(rows, "Ig_mean_A")
    print(f"REPORT_CODE: {code}")
    print(
        f"STAGE_SUMMARY: stage={stage} rows={len(rows)} "
        f"max_abs_Id_A={max_id:.6e} max_abs_Ig_A={max_ig:.6e}"
    )
    print(f"OUTPUT_CSV: {out_csv}")
    return StageSummary(stage, out_csv, len(rows), max_id, max_ig, code)


def _json_safe_float(value: float) -> float | None:
    return None if math.isnan(value) else value


def write_report_code(directory: Path, summary: StageSummary) -> Path:
    """Persist a small machine-readable summary next to stage CSV output."""

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "report_code.json"
    payload = {
        "stage": summary.stage,
        "report_code": summary.report_code,
        "rows": summary.rows,
        "output_csv": str(summary.out_csv),
        "max_abs_Id_A": _json_safe_float(summary.max_abs_id_a),
        "max_abs_Ig_A": _json_safe_float(summary.max_abs_ig_a),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return path


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    if text and all(ch.isalnum() or ch in "._-/+ " for ch in text) and not text.startswith(("-", "?", "@", "`")):
        return text
    return json.dumps(text, ensure_ascii=False)


def _yaml_lines(value: Any, indent: int = 0) -> list[str]:
    sp = "  " * indent
    if isinstance(value, Mapping):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                lines.append(f"{sp}{key}:")
                lines.extend(_yaml_lines(item, indent + 1))
            elif isinstance(item, (list, tuple)):
                lines.append(f"{sp}{key}:")
                if not item:
                    lines[-1] += " []"
                for elem in item:
                    if isinstance(elem, Mapping):
                        lines.append(f"{sp}  -")
                        lines.extend(_yaml_lines(elem, indent + 2))
                    else:
                        lines.append(f"{sp}  - {_yaml_scalar(elem)}")
            else:
                lines.append(f"{sp}{key}: {_yaml_scalar(item)}")
        return lines
    return [f"{sp}{_yaml_scalar(value)}"]


def write_manifest_yaml(directory: Path, manifest: Mapping[str, Any]) -> Path:
    """Write a small dependency-free YAML manifest next to stage outputs."""

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.yaml"
    path.write_text("\n".join(_yaml_lines(manifest)) + "\n", encoding="utf-8")
    return path


def write_summary_md(directory: Path, summary: StageSummary, *, manifest_path: Path | None = None) -> Path:
    """Write a short human-readable run summary next to machine outputs."""

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "summary.md"
    lines = [
        f"# {summary.stage}",
        "",
        f"- report_code: `{summary.report_code}`",
        f"- rows: {summary.rows}",
        f"- output_csv: `{summary.out_csv}`",
        f"- max_abs_Id_A: {_json_safe_float(summary.max_abs_id_a)}",
        f"- max_abs_Ig_A: {_json_safe_float(summary.max_abs_ig_a)}",
    ]
    if manifest_path is not None:
        lines.append(f"- manifest: `{manifest_path}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
