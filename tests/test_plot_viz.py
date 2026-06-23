"""PlotPanel 可视化进阶:导出图片/CSV、按 schema 智能 log 默认、数据表 List 视图。"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def _fefet_csv(tmp_path, delays=(1e-6, 1e-3, 1.0)):
    import pandas as pd

    rows = []
    for d in delays:
        rows.append({"state_target": "ERS", "delay_s": d, "Id_mean_A": 1e-6,
                     "Id_std_A": 1e-8, "Ig_mean_A": 1e-9})
        rows.append({"state_target": "PGM", "delay_s": d, "Id_mean_A": -2e-6,
                     "Id_std_A": 1e-8, "Ig_mean_A": 1e-9})
    p = tmp_path / "r.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    return p


def test_data_table_filled(qapp, tmp_path):
    from gui.plot_panel import PlotPanel

    pp = PlotPanel()
    pp.show_result(str(_fefet_csv(tmp_path)), "fefet_fixedcols", live=False)
    assert pp._table.rowCount() == 6
    assert pp._table.columnCount() == 5


def test_smart_logx_default_for_fefet_delay(qapp, tmp_path):
    pytest.importorskip("pyqtgraph")
    from gui.plot_panel import PlotPanel

    pp = PlotPanel()
    pp.show_result(str(_fefet_csv(tmp_path, delays=(1e-6, 1e-3, 1.0))), "fefet_fixedcols", live=False)
    assert pp._cb_logx.isChecked() is True   # delay 跨数量级 → 默认 log-X


def test_dc_default_logy(qapp, tmp_path):
    pytest.importorskip("pyqtgraph")
    import pandas as pd

    from gui.plot_panel import PlotPanel

    pp = PlotPanel()
    csv = tmp_path / "dc.csv"
    pd.DataFrame({"vg_set": [0, -0.5, -1.0], "id_A": [1e-9, 1e-7, 1e-5],
                  "ig_A": [1e-12, 1e-12, 1e-12]}).to_csv(csv, index=False)
    pp.show_result(str(csv), "dc", live=False)
    assert pp._cb_logy.isChecked() is True   # |Id| → 默认 log-Y


def test_export_image_and_csv(qapp, tmp_path):
    pytest.importorskip("pyqtgraph")
    import pandas as pd

    from gui.plot_panel import PlotPanel

    pp = PlotPanel()
    pp.resize(800, 600)
    pp.show_result(str(_fefet_csv(tmp_path)), "fefet_fixedcols", live=False)

    png = tmp_path / "out.png"
    assert pp.save_result_image(str(png)) is True
    assert png.exists() and png.stat().st_size > 0

    out_csv = tmp_path / "out.csv"
    assert pp.save_result_csv(str(out_csv)) is True
    assert out_csv.exists()
    assert len(pd.read_csv(out_csv)) == 6
