"""DeclaredProtocol ↔ dict(JSON 可序列化)。供 GUI 配方编辑器存盘 / 加载。

纯数据转换,零仪器导入。坏字段在 *_from_dict 抛 ValueError/KeyError,由调用方兜。
"""
from __future__ import annotations

from .schema import (
    DeclaredProtocol,
    DelayStep,
    PulseStep,
    ReadStep,
    ResetStep,
    ScanAxis,
    StopGate,
)


def step_to_dict(step) -> dict:
    if step.kind == "reset":
        return {"kind": "reset", "t": step.t}
    if step.kind == "pulse":
        return {"kind": "pulse", "v": step.v, "width": step.width,
                "sign_by_state": step.sign_by_state}
    if step.kind == "delay":
        return {"kind": "delay", "t": step.t}
    if step.kind == "read":
        return {"kind": "read", "vg_list": list(step.vg_list), "vd": step.vd,
                "n_pts": step.n_pts}
    raise ValueError(f"未知 step.kind={step.kind!r}")


def step_from_dict(d: dict):
    k = d["kind"]
    if k == "reset":
        return ResetStep(t=float(d.get("t", 1e-3)))
    if k == "pulse":
        return PulseStep(v=float(d["v"]), width=float(d["width"]),
                         sign_by_state=bool(d.get("sign_by_state", False)))
    if k == "delay":
        return DelayStep(t=float(d.get("t", 0.0)))
    if k == "read":
        return ReadStep(vg_list=tuple(float(x) for x in d["vg_list"]),
                        vd=float(d["vd"]), n_pts=int(d.get("n_pts", 5)))
    raise ValueError(f"未知 step.kind={k!r}")


def recipe_to_dict(decl: DeclaredProtocol) -> dict:
    d: dict = {
        "id": decl.id, "title": decl.title, "physics": decl.physics,
        "description": decl.description, "group": decl.group,
        "steps": [step_to_dict(s) for s in decl.steps],
        "states": list(decl.states), "reps": decl.reps,
    }
    if decl.scan_axis is not None:
        a = decl.scan_axis
        d["scan_axis"] = {"step_index": a.step_index, "param": a.param,
                          "values": list(a.values), "label": a.label}
    if decl.stop_gate is not None:
        d["stop_gate"] = {"ig_stop_uA": decl.stop_gate.ig_stop_uA}
    return d


def recipe_from_dict(d: dict) -> DeclaredProtocol:
    scan = d.get("scan_axis")
    sg = d.get("stop_gate")
    return DeclaredProtocol(
        id=str(d["id"]),
        title=str(d.get("title") or d["id"]),
        physics=str(d.get("physics", "custom")),
        description=str(d.get("description", "")),
        group=str(d.get("group", "自定义协议")),
        steps=tuple(step_from_dict(s) for s in d.get("steps", ())),
        states=tuple(str(x) for x in d.get("states", ("ERS", "PGM"))),
        reps=int(d.get("reps", 1)),
        scan_axis=(ScanAxis(step_index=int(scan["step_index"]), param=scan["param"],
                            values=tuple(float(x) for x in scan["values"]),
                            label=str(scan.get("label", "scan"))) if scan else None),
        stop_gate=(StopGate(ig_stop_uA=float(sg["ig_stop_uA"])) if sg else None),
    )
