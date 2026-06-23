"""SMU DC 协议族(增量6b)· 把 measurements/dc 的 Id-Vg/Id-Vd 扫描包成引擎 runner。

family="SMU",与 WGFMU 完全分离(不碰 wgfmu_fefet 的任何全局/波形构建)。
- dry:`MockB1500`(无硬件、无 VISA);live:真机后端待器件 → 显式 NotImplementedError(不可能误触真机)。
- 落盘走 orchestration.make_stage_dir 的两级布局 + manifest → GUI RunBrowser 天然扫得到。
- 返回真 `StageSummary`(六字段,out_csv 真落盘)→ 满足引擎门 `cb.on_stage_done(summary, summary.out_csv.parent)`。
收敛/安全门复用引擎门(validate_live_request 对 DC 段照常生效),本模块只管"跑一次扫描 + 落盘"。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..measurements.dc.config import DCSweepConfig
from ..measurements.dc.sweep import DCSweepRunner
from ..orchestration.core import ExperimentContext, StageSpec, StageSummary
from ..orchestration.export import make_stage_dir

_REPO_ROOT = Path(__file__).resolve().parents[3]  # .../B1500(runs/ 所在)

# dry MockB1500 仿真在 ch4(Gate)/ch5(Drain);真机按接线改这三个通道。
DC_GATE_CH, DC_DRAIN_CH, DC_SOURCE_CH = 4, 5, 6
DC_VG_POINTS_DEFAULT = [0.0, -0.5, -1.0, -1.5, -2.0]
DC_VD_POINTS_DEFAULT = [0.0, -0.2, -0.4, -0.6, -0.8, -1.0]
DC_VD_FIXED_DEFAULT = -0.1
DC_VS_FIXED_DEFAULT = 0.0
DC_COLUMNS = ["vg_set", "vd_set", "vs_set", "ig_A", "id_A", "is_A", "err", "status", "timestamp"]


def _floats(v, default) -> list[float]:
    if v is None or v == "":
        return list(default)
    if isinstance(v, (list, tuple)):
        return [float(x) for x in v]
    return [float(p) for p in str(v).split(",") if str(p).strip() != ""]


def _ctx_from_view(view) -> ExperimentContext:
    root = Path(getattr(view, "out_root", "") or _REPO_ROOT)
    return ExperimentContext(
        root=root,
        device_id=getattr(view, "device_id", "DEVICE"),
        geometry=getattr(view, "geometry", ""),
        serial=(getattr(view, "serial", "") or ""),
        live=bool(getattr(view, "live", False)),
        seed=getattr(view, "seed", None),
    )


def _write_manifest(out_dir: Path, stage: str, view) -> None:
    lines = [
        f"stage: {stage}",
        f"device_id: {getattr(view, 'device_id', '')}",
        f"geometry: {getattr(view, 'geometry', '')}",
        f"live: {str(bool(getattr(view, 'live', False))).lower()}",
        "family: SMU",
    ]
    (out_dir / "manifest.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _maxabs(df, col: str) -> float:
    if col not in df.columns or len(df) == 0:
        return 0.0
    a = np.abs(np.asarray(df[col], dtype=float))
    return float(np.nanmax(a)) if a.size else 0.0


def _run_dc(backend, view, *, stage: str, kind: str, callbacks=None) -> StageSummary:
    cfg = DCSweepConfig.from_notebooks_default(
        ch_g=int(getattr(view, "gate_ch", DC_GATE_CH)),
        ch_d=int(getattr(view, "drain_ch", DC_DRAIN_CH)),
        ch_s=int(getattr(view, "smu_s_ch", DC_SOURCE_CH)),
    )
    runner = DCSweepRunner(backend, cfg)
    prog = (lambda c, t: callbacks.on_progress(c, t)) if callbacks is not None else None
    vg = _floats(getattr(view, "dc_vg_points", None), DC_VG_POINTS_DEFAULT)
    vs = float(getattr(view, "dc_vs_fixed", DC_VS_FIXED_DEFAULT))
    if kind == "idvg":
        vd = float(getattr(view, "dc_vd_fixed", DC_VD_FIXED_DEFAULT))
        df = runner.sweep_vg(vg, vd, vs, progress_callback=prog)
    else:
        vd_pts = _floats(getattr(view, "dc_vd_points", None), DC_VD_POINTS_DEFAULT)
        df = runner.sweep_vd(vg, vd_pts, vs, progress_callback=prog)

    out_dir = make_stage_dir(_ctx_from_view(view), stage)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "data.csv"
    df.to_csv(out_csv, index=False, encoding="utf-8")   # UTF-8 无 BOM(增量3 口径)
    _write_manifest(out_dir, stage, view)

    if callbacks is not None:
        try:
            callbacks.on_shot(stage, 0, df.to_dict("records"))  # 给 GUI 一个"完成可绘"信号
        except Exception:  # noqa: BLE001
            pass
    return StageSummary(stage=stage, out_csv=out_csv, rows=int(len(df)),
                        max_abs_id_a=_maxabs(df, "id_A"), max_abs_ig_a=_maxabs(df, "ig_A"),
                        report_code=f"{stage}_DONE")


def run_dc_idvg(backend, view, *, callbacks=None) -> StageSummary:
    return _run_dc(backend, view, stage="DC_IDVG", kind="idvg", callbacks=callbacks)


def run_dc_idvd(backend, view, *, callbacks=None) -> StageSummary:
    return _run_dc(backend, view, stage="DC_IDVD", kind="idvd", callbacks=callbacks)


SMU_STAGE_REGISTRY = {
    "DC_IDVG": StageSpec("DC_IDVG", "DC_IdVg_sweep", "SMU Id-Vg DC sweep (transfer)", run_dc_idvg),
    "DC_IDVD": StageSpec("DC_IDVD", "DC_IdVd_sweep", "SMU Id-Vd DC sweep (output)", run_dc_idvd),
}


def make_backend_for(family: str, live: bool):
    """按 family 选后端。SMU dry → MockB1500;SMU live → 待器件;WGFMU → 原路径(一字不改)。"""
    if family == "SMU":
        if live:
            raise NotImplementedError("SMU live backend pending hardware bring-up(真机后端待器件)")
        from ..measurements.dc.testing_utils import MockB1500
        return MockB1500(), "DUMMY::SMU"
    from .wgfmu_fefet import make_backend
    return make_backend(live)
