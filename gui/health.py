"""器件状态软判定(只判 + 记录 + 提示,从不拦)。

哲学(椰椰 2026-06-24):器件死亡是排程约束、不是研究对象。这里只从读数里看出
击穿 / 窗塌 / 未导通,给个软提示并记一行,操作员自己决定继续 / 跳过 / 换针——
**绝不 raise、绝不挡流程**(连 S1 都能跳)。要分析最后从数据(CSV + run_log)做,
不建台账、不做死因分析、不做寿命建模。

阈值默认可改:
  conduction_uA = 5.0   主读点 |Id| ≥ 此值才算"导通"(S1 体检 / 写后弱窗参考)
  collapse_k    = 3.0   |Id| < k×Id_std(信号没过噪声)且 Ig 健康 → 窗塌(态丢失,非击穿)
  ig_warn_uA    = 5.0   |Ig| ≥ 此值 → 疑似击穿(引擎层另有硬停门护硬件,这里只提示)
"""
from __future__ import annotations

DEFAULTS = {"conduction_uA": 5.0, "collapse_k": 3.0, "ig_warn_uA": 5.0}

_LABEL = {
    "ok": "正常",
    "breakdown": "疑似击穿(Ig 高)",
    "collapse": "疑似窗塌(Id 没过噪声、Ig 健康 = 态丢失非击穿)",
    "low_id": "Id 偏小(S1=未见导通 / 写后=弱窗,留意)",
    "no_data": "无有效读数",
}


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None   # NaN -> None


def _near(a, b):
    a = _num(a)
    return a is not None and abs(a - b) < 1e-6


def assess(rows, *, main_vg: float = -1.0, conduction_uA: float = 5.0,
           collapse_k: float = 3.0, ig_warn_uA: float = 5.0) -> dict:
    """对一组读行给软判定。取主读点(Vg≈main_vg)的最坏情形;无主读点则用全部行。

    返回 {status, min_id_a, max_ig_a, id_std_a, label}。
    status ∈ {ok, breakdown, collapse, low_id, no_data}。**从不抛异常。**
    """
    rows = list(rows or [])
    main = [r for r in rows if _near(r.get("Vg_read_V"), main_vg)]
    src = main or rows
    igs = [abs(v) for r in src if (v := _num(r.get("Ig_mean_A"))) is not None]
    ids = [(abs(v), abs(_num(r.get("Id_std_A")) or 0.0))
           for r in src if (v := _num(r.get("Id_mean_A"))) is not None]
    max_ig = max(igs) if igs else 0.0
    if not ids:
        return {"status": "no_data", "min_id_a": None, "max_ig_a": max_ig,
                "id_std_a": None, "label": _LABEL["no_data"]}
    id_min, id_std = min(ids, key=lambda t: t[0])
    if max_ig >= ig_warn_uA * 1e-6:
        status = "breakdown"
    elif id_min < collapse_k * id_std:
        status = "collapse"
    elif id_min < conduction_uA * 1e-6:
        status = "low_id"
    else:
        status = "ok"
    return {"status": status, "min_id_a": id_min, "max_ig_a": max_ig,
            "id_std_a": id_std, "label": _LABEL[status]}
