"""Plan(预演)时序预览:从 dry 模式协议自己 build 出的 WGFMU 波形里,
抽出 上升/下降沿 · 写 · 读点 · 各 delay · 总时长 · 向量数 给操作员看。

不是重新推导参数,而是用**协议自己的 build**——经 AuditBackend 记录的
create_pattern / add_vector / set_measure_event——所以预览的这条波形 =
live 时会真正下发的同一条。dry 跑一遍、记录每次 execute 的各段波形,再挑
"含读窗最多"的那段当时间线代表(E1S/E6S 一段;E6M 取某个 checkpoint 读段)。

`build_timing_preview` 从不抛异常:失败回 {"ok": False, "error": ...}。
"""
from __future__ import annotations

import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

from fefetlab.engine import REGISTRY, ProtocolEngine
from fefetlab.measurements.wgfmu.audit_backend import AuditBackend
from fefetlab.protocols import wgfmu_fefet as base


class _CaptureBackend(AuditBackend):
    """dry 后端:记录每一次 execute() 当时的 patterns/events(整条实验的各段波形)。

    单写 E1S/E6S 是一段(写+全部读在一条 pattern);E6M 是多段(写 + 各 N 块扰动 +
    checkpoint 读),所以要全收,再挑"含读窗最多"的那段当时间线代表。
    """

    def __init__(self, **kw):
        super().__init__(**kw)
        self.shots: list[dict] = []

    def execute(self):
        self.shots.append({
            "patterns": deepcopy(self._patterns),
            "events": deepcopy(self._events),
        })
        return super().execute()


def default_params_for(stage: str) -> dict:
    """全量默认 ∪ REGISTRY 默认 ∪ 最小身份,凑一份能 dry 跑的参数(GUI 用表单值覆盖)。

    WGFMU/SMU 协议先铺 `parse_args([])` 全集——runner 会读一些**没暴露成表单**的键
    (如 E4/E5 的 `e1_wide_vg`),只用 REGISTRY 暴露的参数会缺键 → AttributeError。
    与 worker(engine_worker.py)凑参数的口径保持一致。
    """
    spec = REGISTRY[stage]
    params: dict = {}
    if spec.family in ("WGFMU", "SMU"):
        try:
            from fefetlab.protocols.wgfmu_fefet import parse_args
            params.update(vars(parse_args([])))
        except Exception:  # noqa: BLE001
            pass
    params.update({ps.name: ps.default for ps in spec.params})
    params.setdefault("device_id", "PREVIEW")
    params.setdefault("geometry", "L10W10")
    for k in ("serial", "device_type", "operator"):
        params.setdefault(k, "")
    params["live"] = False
    return params


def _points(pattern: dict) -> list[tuple[float, float]]:
    """patterns[name] -> [(t, voltage)] 折线端点(含 init_v 起点)。

    AuditBackend 的每个 vector = "从上一终点**线性**斜升/降到 voltage,历时 dt",所以波形
    是分段线性(升降沿 T_RF 是斜边),用端点折线画才忠实——不是阶梯,这样升/降时间看得见。
    """
    pts: list[tuple[float, float]] = [(0.0, float(pattern.get("init_v", 0.0)))]
    t = 0.0
    for dt, v in pattern.get("vectors", []):
        t += dt
        pts.append((t, float(v)))
    return pts


def _features(points, read_times):
    """从折线找非零保持段(平台),分成 脉冲 / 读 两类,各按电压去重(留最宽的代表)。

    用于在时序预览图上把"这是几伏、多宽的脉冲""这里是读点"直接标出来。
    """
    rts = sorted(read_times)
    best: dict = {}
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if v0 != v1 or abs(v0) < 1e-9 or t1 <= t0:
            continue
        is_read = any(t0 <= rt <= t1 for rt in rts)
        key = (round(v0, 4), is_read)
        cand = ((t0 + t1) / 2.0, v0, t1 - t0)
        if key not in best or cand[2] > best[key][2]:
            best[key] = cand
    pulses, reads = [], []
    for (v, is_read), (t, vv, w) in best.items():
        (reads if is_read else pulses).append({"t": t, "v": vv, "width": w})
    pulses.sort(key=lambda d: -abs(d["v"]))
    reads.sort(key=lambda d: d["t"])
    return pulses, reads


def build_timing_preview(stage: str, params: dict | None = None) -> dict:
    """dry 跑一遍,抓协议 build 的各段波形,抽时序摘要 + 时间线(挑含读窗最多的段当代表)。

    **从不抛异常**:失败回 {"ok": False, "error": ...}。可能较慢(高 N E6M 会 build 全部分块),
    调用方(GUI)宜放后台线程,别卡主线程。
    """
    if stage not in REGISTRY:
        return {"ok": False, "error": f"未知协议 {stage}"}
    p = default_params_for(stage)
    if params:
        p.update(params)
    p["live"] = False
    return _capture_extract(lambda b: ProtocolEngine().run(stage, p, backend=b), stage, p)


def preview_declared(decl, params: dict | None = None) -> dict:
    """预览一条**未保存**的声明式配方(GUI 编辑器用):直接 compile_declared 抓波形。从不抛。"""
    from fefetlab.engine.param_view import ParamView
    from fefetlab.protocols.declared.compiler import compile_declared
    from fefetlab.protocols.declared.registry_glue import _validate, default_params_for_decl
    try:
        _validate(decl)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    p = default_params_for_decl(decl)
    if params:
        p.update(params)
    p["live"] = False
    return _capture_extract(lambda b: compile_declared(decl, b, ParamView(p)), decl.id, p)


def _capture_extract(run_fn, stage_label: str, p: dict) -> dict:
    """跑 run_fn(prev_backend)(dry)抓各段波形,抽摘要 + 折线点。**从不抛异常。**"""
    tmp = Path(tempfile.mkdtemp(prefix="plan_preview_"))
    p["out_root"] = str(tmp)
    prev = _CaptureBackend(gate_ch=base.GATE_CH, drain_ch=base.DRAIN_CH,
                           channels=[201, 202, 301, 302])
    prev.open_session("DUMMY::WGFMU")
    prev._fefet_visa_addr = "DUMMY::WGFMU"
    prev._fefet_wgfmu_initialized = False
    err = None
    try:
        run_fn(prev)
    except Exception as exc:  # noqa: BLE001  预览失败不应中断 GUI
        err = f"{type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    shots = prev.shots
    if not shots:
        return {"ok": False, "error": err or "未捕获到波形(协议未 execute)"}

    def _gp(s):
        return s["patterns"].get("gp", {})

    def _vecs(s):
        return _gp(s).get("vectors", [])

    # 时间线代表段 = 含读窗最多的那次 execute(E1S/E6S 只一段;E6M 取某 checkpoint 读段);
    # 若全无读窗,退化为向量最多的那段。
    repr_shot = max(shots, key=lambda s: len(s["events"]))
    if not repr_shot["events"]:
        repr_shot = max(shots, key=lambda s: len(_vecs(s)))
    gp = _gp(repr_shot)
    dp = repr_shot["patterns"].get("dp", {})
    gate_pts = _points(gp)
    drain_pts = _points(dp)
    repr_events = sorted(repr_shot["events"].values(), key=lambda e: e["time_s"])
    total = sum(sum(dt for dt, _ in _vecs(s)) for s in shots)   # 全部段累计时长
    n_vec_max = max((len(_vecs(s)) for s in shots), default=0)   # 单段最大(对照预算)

    def g(*keys):
        for k in keys:
            if k in p and p[k] not in (None, ""):
                return p[k]
        return None

    budget = base.WGFMU_MAX_VECTORS_PER_PATTERN
    summary = {
        "stage": stage_label,
        "t_rf_s": base.T_RF,
        "v_write_V": g("write_v", "v_write"),       # None = ±5V 默认
        "t_write_s": g("t_write_s", "t_write"),      # None = 100µs 默认
        "read_vg_V": g("read_vg", "rich_vg"),
        "t_read_s": g("t_read_s", "t_read"),
        "n_pts": g("n_pts"),
        "vd_read_V": g("vd_read"),
        "delays_s": g("delays", "post_delays", "checkpoints"),
        "interval_s": g("interval_s"),
        "disturb_amp_V": g("disturb_amp"),
        "total_shot_duration_s": total,
        "n_vectors_gate_max": n_vec_max,
        "vector_budget": budget,
        "fits_one_pattern": n_vec_max <= budget,
        "n_executes": len(shots),
        "n_read_events": len(repr_events),
    }
    read_ts = [e["time_s"] for e in repr_events]
    pulses, reads = _features(gate_pts, read_ts)
    return {
        "ok": True,
        "summary": summary,
        "gate_points": gate_pts,
        "drain_points": drain_pts,
        "read_events_s": read_ts,
        "pulses": pulses,     # [{t,v,width}] 写/扰动脉冲(按电压去重),供标注
        "reads": reads,       # [{t,v,width}] 读平台(按电压去重),供标注
        "note": err,
    }
