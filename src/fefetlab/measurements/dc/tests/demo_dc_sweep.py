"""
DC Sweep functional verification script.

This script provides an interactive, step-by-step verification of DC sweep functionality.
Uses simulated data (no actual hardware required) to verify API correctness.

Run: python demo_dc_sweep.py
"""

import sys
import os
from pathlib import Path
from typing import Optional

# Set UTF-8 encoding for Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add fefetlab to path
src_path = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from fefetlab.measurements.dc import (
    DCSweepAPI,
    DCSweepConfig,
    DCChannelConfig,
    DCSweepRunner,
    DCMeasurePoint,
    DCDataExporter,
)
import pandas as pd


class MockB1500:
    """Mock B1500 instrument for testing without hardware."""

    def __init__(self):
        self.channels_connected = set()
        self.voltages = {}
        self.call_count = 0

    def fmt(self, mode):
        """Format mode."""
        print(f"  ✓ fmt({mode})")

    def av(self, count, mode):
        """Averaging."""
        print(f"  ✓ av({count}, {mode})")

    def fl(self, mode):
        """Filter."""
        print(f"  ✓ fl({mode})")

    def cn(self, channels):
        """Connect channels."""
        self.channels_connected = set(channels)
        print(f"  ✓ cn({channels})")

    def dv(self, ch, vrange, voltage, compliance):
        """Set voltage."""
        self.voltages[ch] = voltage
        # print(f"  ✓ dv(CH{ch}, vrange={vrange}, V={voltage:.3f}, I_comp={compliance:.2e})")

    def ti(self, ch, irange=0):
        """Measure current (simulated)."""
        voltage = self.voltages.get(ch, 0.0)
        # Simulate a simple I-V relationship: I = 1e-5 * V^2 (for demonstration)
        if ch == 4:  # Gate
            i = voltage * 1e-8  # Tiny gate leakage
        elif ch == 5:  # Drain
            i = (voltage ** 2) * 1e-5 if voltage < 0 else 1e-6  # Nonlinear
        else:  # Source
            i = 0.0
        return i

    def errx(self):
        """Check error queue."""
        return "0"  # No error

    def dz(self, channels):
        """Zero channels."""
        for ch in channels:
            self.voltages[ch] = 0.0

    def cl(self, channels):
        """Close/disable channels."""
        pass


def test_config_creation():
    """Test 1: Configuration object creation."""
    print("\n" + "=" * 60)
    print("TEST 1: Configuration Creation")
    print("=" * 60)

    config = DCSweepConfig.from_notebooks_default(ch_g=4, ch_d=5, ch_s=6)

    print(f"✓ Created config:")
    print(f"  - Channels: G={config.channels['G'].channel}, "
          f"D={config.channels['D'].channel}, S={config.channels['S'].channel}")
    print(f"  - Delay: {config.delay_s}s")
    print(f"  - Format mode: {config.fmt_mode}")
    print(f"  - Averaging: {config.av_count} samples")

    assert config.channels['G'].channel == 4
    assert config.channels['D'].channel == 5
    assert config.channels['S'].channel == 6

    return config


def test_single_measurement(config: DCSweepConfig):
    """Test 2: Single point measurement."""
    print("\n" + "=" * 60)
    print("TEST 2: Single Point Measurement")
    print("=" * 60)

    mock_b1500 = MockB1500()
    measurer = DCMeasurePoint(mock_b1500, config)

    print("\nMeasuring at: Vg=0V, Vd=0.1V, Vs=0V")
    result = measurer.measure(vg=0.0, vd=0.1, vs=0.0)

    print(f"\n✓ Measurement result:")
    print(f"  - VG={result.vg_set}V, ID={result.id_A:.3e}A, IG={result.ig_A:.3e}A")
    print(f"  - Status: {result.status}")
    print(f"  - Error: {result.err}")

    assert result.status == "ok"
    assert result.id_A is not None
    assert result.ig_A is not None


def test_sweep_execution(config: DCSweepConfig):
    """Test 3: Sweep execution."""
    print("\n" + "=" * 60)
    print("TEST 3: Sweep Execution (Id-Vg)")
    print("=" * 60)

    mock_b1500 = MockB1500()
    mock_b1500.fmt = lambda m: None  # Suppress output
    mock_b1500.av = lambda *a: None
    mock_b1500.fl = lambda m: None

    runner = DCSweepRunner(mock_b1500, config)

    vg_points = [0.0, -0.2, -0.4, -0.6]
    print(f"\nExecuting sweep: {len(vg_points)} points")
    print(f"  Vg: {vg_points}")
    print(f"  Vd (fixed): 0.1V")
    print(f"  Vs (fixed): 0.0V")

    df = runner.sweep_vg(vg_points=vg_points, vd_fixed=0.1, vs_fixed=0.0, progress_callback=None)

    print(f"\n✓ Sweep completed: {len(df)} measurements")
    print(f"\nData preview:")
    print(df[["vg_set", "vd_set", "id_A", "ig_A", "status"]].to_string())

    assert len(df) == len(vg_points)
    assert all(df["status"] == "ok")


def test_data_export(config: DCSweepConfig):
    """Test 4: Data export and QC generation."""
    print("\n" + "=" * 60)
    print("TEST 4: Data Export and QC Generation")
    print("=" * 60)

    mock_b1500 = MockB1500()
    mock_b1500.fmt = lambda m: None
    mock_b1500.av = lambda *a: None
    mock_b1500.fl = lambda m: None

    runner = DCSweepRunner(mock_b1500, config)
    df = runner.sweep_vg(vg_points=[0.0, -0.2, -0.4], vd_fixed=0.1, vs_fixed=0.0)

    exporter = DCDataExporter()
    result = exporter.export_sweep(df, "test_sweep")

    run_dir = result["run_dir"]
    qc_df = result["qc_df"]

    print(f"\n✓ Data exported to: {run_dir}")
    print(f"  - CSV: {result['data_paths']['csv']}")
    print(f"  - JSON: {result['data_paths']['json']}")
    print(f"  - QC: {run_dir / 'qc.csv'}")

    print(f"\nQC Report ({len(qc_df)} items):")
    print(qc_df[["vg_set", "status", "issues"]].to_string())

    assert (run_dir / "data.csv").exists()
    assert (run_dir / "data.json").exists()
    assert (run_dir / "qc.csv").exists()

    # Cleanup
    import shutil

    shutil.rmtree(run_dir)
    print(f"\n✓ Cleaned up test directory")


def test_high_level_api(config: DCSweepConfig):
    """Test 5: High-level API."""
    print("\n" + "=" * 60)
    print("TEST 5: High-Level DCSweepAPI")
    print("=" * 60)

    # Create mock session
    class MockSession:
        pass

    session = MockSession()

    # Manually construct API to use mock
    from fefetlab.instruments.visa_session import VisaSession
    from fefetlab.b1500 import B1500

    # For this test, we'll just verify the API structure
    print("\n✓ DCSweepAPI structure verified:")
    from fefetlab.measurements.dc import DCSweepAPI

    print(f"  - run_idvg_sweep() method available")
    print(f"  - run_idvd_sweep() method available")
    print(f"  - run_custom_sweep() method available")

    # List expected attributes
    expected_methods = ["run_idvg_sweep", "run_idvd_sweep", "run_custom_sweep"]
    for method in expected_methods:
        assert hasattr(DCSweepAPI, method), f"Missing method: {method}"
        print(f"  ✓ {method} exists")


def run_all_tests():
    """Run all verification tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 58 + "║")
    print("║" + "   DC SWEEP API - VERIFICATION TEST SUITE   ".center(58) + "║")
    print("║" + " " * 58 + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        # Test 1: Config
        config = test_config_creation()

        # Test 2: Single measurement
        test_single_measurement(config)

        # Test 3: Sweep
        test_sweep_execution(config)

        # Test 4: Export/QC
        test_data_export(config)

        # Test 5: API structure
        test_high_level_api(config)

        # Summary
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\n✓ DC Sweep API is fully functional and ready to use!")
        print("\nNext steps:")
        print("  1. Run: python scripts/verify_dc_sweep.py")
        print("  2. Or use examples in notebooks/11_dc_api_idvg_example.ipynb")
        print("  3. Read: src/fefetlab/measurements/dc/README.md")

        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
