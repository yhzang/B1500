"""声明式协议编译器(DSL v1)· 把 DeclaredProtocol 编译成 WGFMU 向量并 dry/真机执行。

核心:写相自展开(镜像 run_e1_shot 的双 pattern 写法),读相整段委托给经 golden 验证的
`_build_read_phase` + `_summarize_windows`,执行走 `_configure_and_run_phase`。
**绝不调用 configure_channel_map、绝不写任何 WGFMU 运行时全局**——只读常量/纯函数(R1 隔离)。
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from ...orchestration.core import StageSummary
from ...orchestration.export import make_stage_dir
from ..smu_dc import _ctx_from_view, _floats
from ..wgfmu_fefet import (
    DRAIN_CH,
    GATE_CH,
    N_PTS,
    T_RF,
    _build_read_phase,
    _configure_and_run_phase,
    _summarize_windows,
)
from .schema import DeclaredProtocol, DelayStep, PulseStep, ReadStep, ResetStep


def _finite(x) -> float:
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return 0.0
    return xf if xf == xf else 0.0  # NaN → 0


def _resolve_steps(decl: DeclaredProtocol, state, axis_v):
    steps = list(decl.steps)
    if state:  # sign_by_state 的 pulse:ERS→+|v|, PGM→-|v|
        steps = [
            replace(s, v=(+abs(s.v) if state == "ERS" else -abs(s.v)))
            if (isinstance(s, PulseStep) and s.sign_by_state) else s
            for s in steps
        ]
    if decl.scan_axis is not None and axis_v is not None:  # 扫描轴改写指定 step 的字段
        i = decl.scan_axis.step_index
        steps[i] = replace(steps[i], **{decl.scan_axis.param: axis_v})
    return tuple(steps)


def _write_manifest(out_dir: Path, stage: str, view) -> None:
    lines = [
        f"stage: {stage}",
        f"device_id: {getattr(view, 'device_id', '')}",
        f"geometry: {getattr(view, 'geometry', '')}",
        f"live: {str(bool(getattr(view, 'live', False))).lower()}",
        "family: CUSTOM",
    ]
    (out_dir / "manifest.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def compile_declared(decl: DeclaredProtocol, backend, view, *, callbacks=None) -> StageSummary:
    """把声明式协议编译执行,返回真 StageSummary(out_csv 真落盘)。"""
    ctx = _ctx_from_view(view)
    rep_n = int(getattr(view, "reps", decl.reps) or decl.reps)
    # 扫描轴值:GUI 改了以 view 为准(CSV_LINE → _floats),否则用 decl 默认
    if decl.scan_axis is not None:
        axis_vals = tuple(_floats(getattr(view, decl.scan_axis.label, None), decl.scan_axis.values))
    else:
        axis_vals = (None,)
    states = decl.states or (None,)
    ig_stop = float(getattr(view, f"{decl.id}_ig_stop_uA",
                            decl.stop_gate.ig_stop_uA if decl.stop_gate else 0.0) or 0.0)

    shots = [(st, av, r) for st in states for av in axis_vals for r in range(rep_n)]
    rows: list[dict] = []
    max_id = 0.0
    max_ig = 0.0
    report = f"{decl.id}_DONE"
    seq = 0

    for (state, axis_v, rep) in shots:
        steps = _resolve_steps(decl, state, axis_v)
        backend.clear()
        backend.create_pattern("gp", 0.0)
        backend.create_pattern("dp", 0.0)
        t_prefix = 0.0
        read_step = None
        for s in steps:
            if isinstance(s, ResetStep):
                if s.t > 0:
                    backend.add_vector("gp", s.t, 0.0)
                    backend.add_vector("dp", s.t, 0.0)
                    t_prefix += s.t
            elif isinstance(s, PulseStep):
                for dt, vg in [(T_RF, s.v), (s.width, s.v), (T_RF, 0.0)]:
                    backend.add_vector("gp", dt, vg)
                    backend.add_vector("dp", dt, 0.0)
                    t_prefix += dt
            elif isinstance(s, DelayStep):
                if s.t > 0:
                    backend.add_vector("gp", s.t, 0.0)
                    backend.add_vector("dp", s.t, 0.0)
                    t_prefix += s.t
            elif isinstance(s, ReadStep):
                read_step = s
        if read_step is None:
            raise ValueError(f"{decl.id}: 协议必须含一个 read step")

        # 读相整段委托(零重写、golden 同款);event_offset_s 平移读窗对齐写相后
        windows = _build_read_phase(
            backend,
            vg_reads=list(read_step.vg_list),
            vd_read=read_step.vd,
            t_prefix=0.0,
            n_pts=int(getattr(view, "n_pts", read_step.n_pts) or read_step.n_pts),
            event_offset_s=t_prefix,
        )
        timeout = max(30.0, t_prefix * 3 + 10.0)
        g_df, d_df = _configure_and_run_phase(backend, measure=True, timeout_s=timeout)
        win_rows = _summarize_windows(g_df, d_df, windows)
        for wr in win_rows:
            wr["stage"] = decl.id
            wr["device_id"] = getattr(view, "device_id", "")
            wr["geometry"] = getattr(view, "geometry", "")
            wr["state_target"] = state or ""
            wr["repeat_index"] = rep
            if decl.scan_axis is not None:
                wr[decl.scan_axis.label] = axis_v
            max_id = max(max_id, abs(_finite(wr.get("Id_mean_A"))))
            max_ig = max(max_ig, abs(_finite(wr.get("Ig_mean_A"))))
        rows.extend(win_rows)
        if callbacks is not None:
            callbacks.on_shot(decl.id, seq, win_rows)
        seq += 1
        if ig_stop > 0 and max_ig * 1e6 > ig_stop:
            report = f"{decl.id}_STOP_IG"
            break

    out_dir = make_stage_dir(ctx, decl.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / "data.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False, encoding="utf-8")  # UTF-8 无 BOM
    _write_manifest(out_dir, decl.id, view)
    return StageSummary(stage=decl.id, out_csv=out_csv, rows=len(rows),
                        max_abs_id_a=float(max_id), max_abs_ig_a=float(max_ig), report_code=report)
