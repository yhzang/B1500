"""增量6b:DC(SMU)协议族经引擎门 dry 跑通 + family 分流 + live 门(全 dry,本机可跑)。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fefetlab.engine import ProtocolEngine, REGISTRY, RecordingCallbacks
from fefetlab.measurements.dc.testing_utils import MockB1500
from fefetlab.protocols.smu_dc import DC_COLUMNS, run_dc_idvg


def _params(tmp_path, **over):
    p = {
        "device_id": "GOLDEN_DC", "geometry": "L40W10", "serial": "",
        "gate_ch": 4, "drain_ch": 5, "smu_s_ch": 6,
        "dc_vg_points": "0,-0.5,-1.0,-1.5", "dc_vd_fixed": -0.1, "dc_vs_fixed": 0.0,
        "live": False, "out_root": str(tmp_path),
    }
    p.update(over)
    return p


def test_dc_idvg_dry_through_engine(tmp_path):
    """family 分流:SMU 段不经 configure_channel_map(否则 gate=4 会被 WGFMU 通道铁律拦)。"""
    cb = RecordingCallbacks()
    summary = ProtocolEngine().run("DC_IDVG", _params(tmp_path), backend=MockB1500(), callbacks=cb)
    assert summary.report_code == "DC_IDVG_DONE"
    out = Path(summary.out_csv)
    assert out.exists() and out.name == "data.csv"
    assert (out.parent / "manifest.yaml").exists()
    df = pd.read_csv(out)
    assert list(df.columns) == DC_COLUMNS
    assert len(df) == 4
    assert ("stage_done", "DC_IDVG_DONE") in cb.events


def test_dc_idvd_dry_through_engine(tmp_path):
    summary = ProtocolEngine().run(
        "DC_IDVD", _params(tmp_path, dc_vg_points="0,-1.0", dc_vd_points="0,-0.5,-1.0"),
        backend=MockB1500())
    df = pd.read_csv(summary.out_csv)
    assert len(df) == 2 * 3  # vg × vd 网格


def test_dc_family_registered():
    assert REGISTRY["DC_IDVG"].family == "SMU"
    assert REGISTRY["DC_IDVG"].csv_schema == "dc"
    assert REGISTRY["DC_IDVG"].runner is run_dc_idvg


def test_dc_live_without_confirm_blocked(tmp_path):
    """DC 段不绕过 live 门:live=True + confirm="" → StopGate(validate_live_request)。"""
    from fefetlab.orchestration.core import StopGate

    with pytest.raises(StopGate):
        ProtocolEngine().run("DC_IDVG", _params(tmp_path, live=True), backend=MockB1500(), confirm="")
