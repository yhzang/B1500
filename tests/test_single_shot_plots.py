"""单写族专用绘图器:E6M(Id vs N)/ E6S(Id vs 扰后延迟)注册 + 喂样本不抛。"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def test_disturb_plotters_registered_and_run(qapp):
    pytest.importorskip("pyqtgraph")
    import pandas as pd
    import pyqtgraph as pg

    from gui import adapters  # noqa: F401  触发注册
    from gui.plot_dispatch import get_plotter

    for schema in ("fefet_disturb_accum", "fefet_disturb_single"):
        assert get_plotter(schema) is not None, f"{schema} 未注册"

    e6m = pd.DataFrame({
        "state_target": ["ERS", "ERS", "PGM", "PGM"], "n_disturb": [1, 10, 1, 10],
        "Vg_read_V": [-1.0, -1.0, -1.0, -1.0], "Id_mean_A": [1e-6, 9e-7, 2e-6, 2.1e-6],
        "Ig_mean_A": [1e-9, 1e-9, 1e-9, 1e-9],
    })
    w = pg.PlotWidget()
    get_plotter("fefet_disturb_accum")(e6m, w, live=False, options={"show_id": True, "show_ig": True})
    assert len(w.listDataItems()) >= 2   # ERS/PGM 两线

    e6s = pd.DataFrame({
        "state_target": ["ERS", "ERS"], "phase": ["post", "post"],
        "delay_after_disturb_s": [1e-6, 1e-2], "Vg_read_V": [-1.0, -1.0],
        "Id_mean_A": [1e-6, 1.1e-6],
    })
    w2 = pg.PlotWidget()
    get_plotter("fefet_disturb_single")(e6s, w2, live=False, options={"show_id": True})
    assert len(w2.listDataItems()) >= 1


def test_registry_single_shot_schemas():
    from fefetlab.engine import REGISTRY
    assert REGISTRY["E6M"].csv_schema == "fefet_disturb_accum"
    assert REGISTRY["E6S"].csv_schema == "fefet_disturb_single"
    assert REGISTRY["E1S"].csv_schema == "fefet_fixedcols"
