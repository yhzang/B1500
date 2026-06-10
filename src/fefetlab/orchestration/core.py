from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


def _slug(value: str) -> str:
    keep = []
    for ch in str(value):
        keep.append(ch if ch.isalnum() or ch in ("-", "_") else "_")
    out = "".join(keep).strip("_")
    return out or "device"


class StopGate(RuntimeError):
    """Raised when a stage must stop before the next shot/stage."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ExperimentContext:
    """Shared run context for script wrappers and package-level adapters.

    器件身份(2026-06-10 两级归集)分两层:
      * ``device_id``  = 批次/自命名,如 ``"微所pfefet2026"`` —— 顶层归集文件夹(``device_slug``)。
      * ``geometry`` + ``serial`` = 批次内**具体一颗器件**(die),如 L10W40 第 41 号 —— 二级文件夹
        (``die_slug`` = ``L10W40_41``)。``serial`` 缺省为空时 ``die_slug`` 退化为纯几何。
    """

    root: Path
    device_id: str
    geometry: str
    serial: str = ""
    live: bool = False
    seed: int | None = None

    @property
    def device_slug(self) -> str:
        """批次/自命名,顶层归集文件夹,如 微所pfefet2026。"""
        return _slug(self.device_id)

    @property
    def die_slug(self) -> str:
        """批次内具体一颗器件 = 几何[_序号],如 L10W40_41;无序号时退化为纯几何。"""
        s = str(self.serial).strip()
        base = str(self.geometry)
        return _slug(f"{base}_{s}" if s else base)


@dataclass(frozen=True)
class StageSpec:
    """Registry entry for a named experiment stage.

    The runner is intentionally just a callable so scripts can register their
    own backend-specific functions without importing instruments here.
    """

    name: str
    output_label: str
    description: str
    runner: Callable[..., StageSummary]


@dataclass(frozen=True)
class StageSummary:
    stage: str
    out_csv: Path
    rows: int
    max_abs_id_a: float
    max_abs_ig_a: float
    report_code: str


@dataclass(frozen=True)
class StopGatePolicy:
    """Threshold gate over a numeric metric in stage rows.

    Values are interpreted as SI units.  For Ig policies, pass threshold in A
    and an explicit threshold_label such as ``"20UA"`` to preserve legacy
    report codes used by the WGFMU CLI.
    """

    metric: str
    threshold: float
    abs_value: bool = True
    threshold_label: str | None = None
    op: str = ">"

    def _values(self, rows: Iterable[Mapping[str, Any]]) -> list[float]:
        values: list[float] = []
        for row in rows:
            raw = row.get(self.metric, float("nan"))
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if math.isnan(value):
                continue
            values.append(abs(value) if self.abs_value else value)
        return values

    def _metric_code(self) -> str:
        normalized = self.metric.lower()
        if normalized in {"ig", "ig_mean_a", "max_abs_ig_a"}:
            return "IG"
        if normalized in {"id", "id_mean_a", "max_abs_id_a"}:
            return "ID"
        return "".join(ch if ch.isalnum() else "_" for ch in self.metric).strip("_").upper()

    def check(self, rows: Iterable[Mapping[str, Any]], stage: str) -> None:
        values = self._values(rows)
        if not values:
            return
        observed = max(values)
        if self.op != ">":
            raise ValueError(f"unsupported StopGatePolicy op: {self.op!r}")
        if observed > self.threshold:
            label = self.threshold_label or f"{self.threshold:g}"
            metric_code = self._metric_code()
            raise StopGate(
                f"{stage}_STOP_{metric_code}_GT_{label}",
                f"max |{self.metric}|={observed:.3e} > {self.threshold:.3e}",
            )


def validate_live_request(stage: str, live: bool, confirm: str) -> None:
    """Enforce the project rule: live hardware is one confirmed stage at a time."""

    if not live:
        return
    if stage == "ALL_DRY":
        raise StopGate(
            "SETUP_STOP_LIVE_ALL_FORBIDDEN",
            "Live mode is intentionally one stage at a time.",
        )
    if confirm != stage:
        raise StopGate(
            f"SETUP_STOP_CONFIRM_REQUIRED_{stage}",
            f"For live mode, rerun with --live --confirm {stage}.",
        )
