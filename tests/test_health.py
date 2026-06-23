"""器件软判定 assess():击穿/窗塌/未导通/正常,且从不抛异常。"""
from __future__ import annotations

from gui.health import DEFAULTS, assess


def _row(vg, id_mean, id_std=1e-8, ig=1e-9):
    return {"Vg_read_V": vg, "Id_mean_A": id_mean, "Id_std_A": id_std, "Ig_mean_A": ig}


def test_ok():
    rows = [_row(-1.0, 8e-6), _row(-0.5, 4e-6)]
    assert assess(rows, **DEFAULTS)["status"] == "ok"


def test_breakdown_high_ig():
    rows = [_row(-1.0, 8e-6, ig=2e-5)]   # Ig 20µA ≥ 5µA
    assert assess(rows, **DEFAULTS)["status"] == "breakdown"


def test_collapse_signal_below_noise():
    rows = [_row(-1.0, 2e-8, id_std=1e-8, ig=1e-9)]  # |Id|=2e-8 < 3×1e-8, Ig 健康
    assert assess(rows, **DEFAULTS)["status"] == "collapse"


def test_low_id_no_conduction():
    # |Id|=2µA < 5µA 导通阈,但 > 3×Id_std(信号过噪声)→ low_id 非 collapse
    rows = [_row(-1.0, 2e-6, id_std=1e-9, ig=1e-9)]
    assert assess(rows, **DEFAULTS)["status"] == "low_id"


def test_main_vg_picked():
    # 主读点 -1.0 窗塌,旁点 -0.5 正常 → 取主读点判窗塌
    rows = [_row(-1.0, 1e-8, id_std=1e-8), _row(-0.5, 9e-6)]
    assert assess(rows, **DEFAULTS)["status"] == "collapse"


def test_never_raises_on_garbage():
    assert assess([], **DEFAULTS)["status"] == "no_data"
    assert assess([{"Vg_read_V": "x", "Id_mean_A": None}])["status"] == "no_data"


def test_thresholds_adjustable():
    rows = [_row(-1.0, 3e-6)]   # 3µA
    assert assess(rows, conduction_uA=5.0)["status"] == "low_id"   # 默认 5µA → 偏小
    assert assess(rows, conduction_uA=2.0)["status"] == "ok"       # 调到 2µA → 正常
