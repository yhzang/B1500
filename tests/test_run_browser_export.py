"""RunBrowser 导出图 + 回流项目4(复制 CSV/manifest,统一 UTF-8 无 BOM)。"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def _mk_run(tmp_path, bom_csv=False):
    d = tmp_path / "runs" / "DEV" / "die1" / "dry" / "20260101_000000_E1"
    d.mkdir(parents=True)
    enc = "utf-8-sig" if bom_csv else "utf-8"
    (d / "e1.csv").write_text("state_target,delay_s,Id_mean_A\nERS,1e-3,1e-6\n", encoding=enc)
    (d / "manifest.yaml").write_text("stage: E1\ndevice_id: DEV\n", encoding="utf-8")
    return d


def test_reflow_run_to_strips_bom(qapp, tmp_path):
    pytest.importorskip("pyqtgraph")
    from gui.run_browser_panel import RunBrowserPanel, scan_runs

    _mk_run(tmp_path, bom_csv=True)        # 源 CSV 带 BOM
    panel = RunBrowserPanel(root=str(tmp_path))
    entries = scan_runs(str(tmp_path))
    assert entries
    dst = panel.reflow_run_to(entries[0], tmp_path / "p4")
    out_csv = dst / "e1.csv"
    assert out_csv.exists()
    assert not out_csv.read_bytes().startswith(b"\xef\xbb\xbf")   # 回流后无 BOM
    assert (dst / "manifest.yaml").exists()


def test_run_browser_save_image(qapp, tmp_path):
    pytest.importorskip("pyqtgraph")
    from gui.run_browser_panel import RunBrowserPanel, scan_runs

    _mk_run(tmp_path)
    panel = RunBrowserPanel(root=str(tmp_path))
    panel.resize(700, 500)
    panel._plot_single(scan_runs(str(tmp_path))[0])
    png = tmp_path / "rb.png"
    assert panel.save_plot_image(str(png)) is True
    assert png.exists() and png.stat().st_size > 0
