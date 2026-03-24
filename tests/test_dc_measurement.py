"""
Unit tests for DC measurement functionality.

Tests DC sweep API, configuration, measurement, and export using MockB1500.
Run with: pytest tests/test_dc_measurement.py -v
"""

import pytest
import pandas as pd
from pathlib import Path
import shutil

from fefetlab.measurements.dc import (
    DCSweepConfig,
    DCChannelConfig,
    DCSweepRunner,
    DCMeasurePoint,
    DCDataExporter,
)
from fefetlab.measurements.dc.testing_utils import MockB1500


@pytest.fixture
def mock_b1500():
    """Fixture: Mock B1500 instrument."""
    return MockB1500()


@pytest.fixture
def dc_config():
    """Fixture: Default DC sweep configuration."""
    return DCSweepConfig.from_notebooks_default(ch_g=4, ch_d=5, ch_s=6)


@pytest.fixture
def sweep_runner(mock_b1500, dc_config):
    """Fixture: DC sweep runner with mock instrument."""
    return DCSweepRunner(mock_b1500, dc_config)


@pytest.fixture
def data_exporter(tmp_path):
    """Fixture: Data exporter using temporary directory."""
    return DCDataExporter(export_dir=tmp_path)


# ============================================================================
# Configuration Tests
# ============================================================================


def test_config_creation(dc_config):
    """Test configuration object creation."""
    assert dc_config.channels['G'].channel == 4
    assert dc_config.channels['D'].channel == 5
    assert dc_config.channels['S'].channel == 6
    assert dc_config.delay_s > 0
    assert dc_config.fmt_mode in [1, 2, 12]


def test_channel_config():
    """Test channel configuration object."""
    ch = DCChannelConfig(channel=4, vrange=20, compliance=1e-3)
    assert ch.channel == 4
    assert ch.vrange == 20
    assert ch.compliance == 1e-3


# ============================================================================
# MockB1500 Tests
# ============================================================================


def test_mock_b1500_voltage_setting(mock_b1500):
    """Test mock B1500 voltage setting and retrieval."""
    mock_b1500.dv(4, 0, -0.5, 1e-3)
    mock_b1500.dv(5, 0, 0.1, 1e-3)

    assert mock_b1500.voltages[4] == -0.5
    assert mock_b1500.voltages[5] == 0.1


def test_mock_b1500_current_measurement(mock_b1500):
    """Test mock B1500 current measurement simulation."""
    # Set gate voltage and measure
    mock_b1500.dv(4, 0, -0.5, 1e-3)
    ig = mock_b1500.ti(4)
    assert ig != 0  # Should return simulated leakage current

    # Set drain voltage and measure
    mock_b1500.dv(5, 0, -0.5, 1e-3)
    id = mock_b1500.ti(5)
    assert id > 0  # Should return simulated drain current


def test_mock_b1500_zero_channels(mock_b1500):
    """Test zeroing channels."""
    mock_b1500.dv(4, 0, -0.5, 1e-3)
    mock_b1500.dv(5, 0, 0.1, 1e-3)
    mock_b1500.dz([4, 5, 6])

    assert mock_b1500.voltages[4] == 0.0
    assert mock_b1500.voltages[5] == 0.0
    assert mock_b1500.voltages[6] == 0.0


def test_mock_b1500_error_check(mock_b1500):
    """Test error checking always returns no error."""
    assert mock_b1500.errx() == "0"


# ============================================================================
# Single Point Measurement Tests
# ============================================================================


def test_single_point_measurement(mock_b1500, dc_config):
    """Test single point DC measurement."""
    measurer = DCMeasurePoint(mock_b1500, dc_config)
    result = measurer.measure(vg=0.0, vd=0.1, vs=0.0)

    assert result.vg_set == 0.0
    assert result.vd_set == 0.1
    assert result.vs_set == 0.0
    assert result.id_A is not None
    assert result.ig_A is not None
    assert result.status == "ok"
    assert result.err == "0"


def test_measurement_with_negative_voltages(mock_b1500, dc_config):
    """Test measurement with negative voltages."""
    measurer = DCMeasurePoint(mock_b1500, dc_config)
    result = measurer.measure(vg=-0.5, vd=-0.2, vs=0.0)

    assert result.vg_set == -0.5
    assert result.vd_set == -0.2
    assert result.id_A is not None
    assert result.ig_A is not None
    assert result.status == "ok"


# ============================================================================
# Sweep Tests
# ============================================================================


def test_id_vg_sweep(sweep_runner):
    """Test Id-Vg sweep (transfer characteristics)."""
    vg_points = [0.0, -0.2, -0.4, -0.6]
    df = sweep_runner.sweep_vg(
        vg_points=vg_points,
        vd_fixed=0.1,
        vs_fixed=0.0
    )

    assert len(df) == len(vg_points)
    assert list(df.columns) == ['vg_set', 'vd_set', 'vs_set', 'id_A', 'ig_A', 'status', 'err']
    assert all(df['status'] == 'ok')
    assert all(df['vd_set'] == 0.1)
    assert all(df['vs_set'] == 0.0)


def test_id_vd_sweep(sweep_runner):
    """Test Id-Vd sweep (output characteristics)."""
    vg_points = [0.0, -0.5]
    vd_points = [0.0, 0.1, 0.2]

    df = sweep_runner.sweep_vd(
        vg_points=vg_points,
        vd_points=vd_points,
        vs_fixed=0.0
    )

    expected_points = len(vg_points) * len(vd_points)
    assert len(df) == expected_points
    assert all(df['status'] == 'ok')
    assert all(df['vs_set'] == 0.0)


def test_custom_sweep(sweep_runner):
    """Test custom sweep pattern."""
    sweep_points = [
        (0.0, 0.1, 0.0),
        (-0.2, 0.1, 0.0),
        (-0.4, 0.2, 0.0),
    ]

    df = sweep_runner.sweep_custom(sweep_points=sweep_points)

    assert len(df) == len(sweep_points)
    assert all(df['status'] == 'ok')
    assert df.iloc[0]['vg_set'] == 0.0
    assert df.iloc[1]['vg_set'] == -0.2
    assert df.iloc[2]['vd_set'] == 0.2


def test_sweep_with_progress_callback(sweep_runner):
    """Test sweep with progress callback."""
    progress_calls = []

    def progress_callback(current, total):
        progress_calls.append((current, total))

    vg_points = [0.0, -0.2, -0.4]
    df = sweep_runner.sweep_vg(
        vg_points=vg_points,
        vd_fixed=0.1,
        vs_fixed=0.0,
        progress_callback=progress_callback
    )

    assert len(df) == len(vg_points)
    assert len(progress_calls) > 0  # Progress callback was called


# ============================================================================
# Data Export Tests
# ============================================================================


def test_data_export(data_exporter, sweep_runner):
    """Test data export functionality."""
    # Create sweep data
    vg_points = [0.0, -0.2, -0.4]
    df = sweep_runner.sweep_vg(
        vg_points=vg_points,
        vd_fixed=0.1,
        vs_fixed=0.0
    )

    # Export data
    result = data_exporter.export_sweep(df, "test_sweep")

    # Check results
    assert 'run_dir' in result
    assert 'data_paths' in result
    assert 'qc_df' in result

    run_dir = result['run_dir']
    assert run_dir.exists()
    assert (run_dir / "data.csv").exists()
    assert (run_dir / "data.json").exists()
    assert (run_dir / "qc.csv").exists()

    # Check QC report
    qc_df = result['qc_df']
    assert len(qc_df) == len(vg_points)
    assert all(qc_df['status'] == 'ok')


def test_export_data_integrity(data_exporter, sweep_runner):
    """Test exported data integrity."""
    # Create and export data
    vg_points = [0.0, -0.2]
    df_original = sweep_runner.sweep_vg(
        vg_points=vg_points,
        vd_fixed=0.1,
        vs_fixed=0.0
    )

    result = data_exporter.export_sweep(df_original, "test_integrity")

    # Read back CSV
    csv_path = result['data_paths']['csv']
    df_loaded = pd.read_csv(csv_path)

    # Verify data matches
    assert len(df_loaded) == len(df_original)
    assert list(df_loaded.columns) == list(df_original.columns)
    assert df_loaded['vg_set'].tolist() == df_original['vg_set'].tolist()


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


def test_empty_sweep():
    """Test handling of empty sweep points."""
    mock = MockB1500()
    config = DCSweepConfig.from_notebooks_default(4, 5, 6)
    runner = DCSweepRunner(mock, config)

    df = runner.sweep_vg(vg_points=[], vd_fixed=0.1, vs_fixed=0.0)
    assert len(df) == 0


def test_single_point_sweep(sweep_runner):
    """Test sweep with single point."""
    df = sweep_runner.sweep_vg(
        vg_points=[0.0],
        vd_fixed=0.1,
        vs_fixed=0.0
    )

    assert len(df) == 1
    assert df.iloc[0]['status'] == 'ok'


# ============================================================================
# Integration Test
# ============================================================================


def test_full_workflow_idvg(mock_b1500, dc_config, data_exporter):
    """Integration test: Complete Id-Vg workflow."""
    # 1. Setup
    runner = DCSweepRunner(mock_b1500, dc_config)

    # 2. Execute sweep
    vg_points = [0.0, -0.2, -0.4, -0.6]
    df = runner.sweep_vg(
        vg_points=vg_points,
        vd_fixed=0.1,
        vs_fixed=0.0
    )

    # 3. Export data
    result = data_exporter.export_sweep(df, "integration_test")

    # 4. Verify results
    assert len(df) == len(vg_points)
    assert all(df['status'] == 'ok')
    assert result['run_dir'].exists()

    qc_df = result['qc_df']
    assert all(qc_df['status'] == 'ok')
    assert len(qc_df) == len(vg_points)
