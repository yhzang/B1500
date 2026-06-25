"""Plan(预演)时序预览:从 dry 模式协议自己 build 出的 WGFMU 波形里,
抽出 上升/下降沿 · 写 · 读点 · 各 delay · 总时长 · 向量数 给操作员看。

不是重新推导参数,而是用**协议自己的 build**——经 AuditBackend 记录的
create_pattern / add_vector / set_measure_event——所以预览的这条波形 =
live 时会真正下发的同一条(首写律:抓第一次 execute 的那一炮)。

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
    """REGISTRY 默认 + 最小身份,凑一份能 dry 跑的参数(GUI 用表单值覆盖)。"""
    params: dict = {ps.name: ps.default for ps in REGISTRY[stage].params}
    params.setdefault("device_id", "PREVIEW")
    params.setdefault("geometry", "L10W10")
    for k in ("serial", "device_type", "operator"):
        params.setdefault(k, "")
    params["live"] = False
    return params


def _timeline(pattern: dict) -> list[tuple[float, float, float]]:
    """patterns[name] -> [(t_start, t_end, voltage)] 阶梯段。"""
    segs: list[tuple[float, float, float]] = []
    t = 0.0
    for dt, v in pattern.get("vectors", []):
        segs.append((t, t + dt, v))
        t += dt
    return segs


def build_timing_preview(stage: str, params: dict | None = None) -> dict:
    """dry 跑一遍抓第一炮波形,抽时序摘要 + 时间线。**从不抛异常。**"""
    if stage not in REGISTRY:
        return {"ok": False, "error": f"未知协议 {stage}"}
    p = default_params_for(stage)
    if params:
        p.update(params)
    p["live"] = False
    tmp = Path(tempfile.mkdtemp(prefix="plan_preview_"))
    p["out_root"] = str(tmp)
    prev = _CaptureBackend(gate_ch=base.GATE_CH, drain_ch=base.DRAIN_CH,
                           channels=[201, 202, 301, 302])
    prev.open_session("DUMMY::WGFMU")
    prev._fefet_visa_addr = "DUMMY::WGFMU"
    prev._fefet_wgfmu_initialized = False
    err = None
    try:
        ProtocolEngine().run(stage, p, backend=prev)
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
    gate_tl = _timeline(gp)
    drain_tl = _timeline(dp)
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
        "stage": stage,
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
    return {
        "ok": True,
        "summary": summary,
        "gate_timeline": gate_tl,
        "drain_timeline": drain_tl,
        "read_events_s": [e["time_s"] for e in repr_events],
        "note": err,
    }
