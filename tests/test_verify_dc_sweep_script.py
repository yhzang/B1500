"""Tests for the manual verification script helpers."""

from scripts.verify_dc_sweep import build_dc_config_display_lines
from fefetlab.measurements.dc import DCSweepConfig


def test_build_dc_config_display_lines_show_filter_default_and_reserved_integration():
    cfg = DCSweepConfig.from_notebooks_default(4, 5, 6)

    lines = build_dc_config_display_lines(cfg)

    assert any("Channels: G=CH4, D=CH5, S=CH6" in line for line in lines)
    assert any("Filter: ON (fl_mode=1)" in line for line in lines)
    assert any("Integration time: unset (reserved config only)" in line for line in lines)



def test_build_dc_config_display_lines_show_explicit_integration_settings():
    cfg = DCSweepConfig.from_notebooks_default(4, 5, 6)
    cfg.integration_time_mode = "PLC"
    cfg.integration_time_factor = 2.0

    lines = build_dc_config_display_lines(cfg)

    assert any("Integration time: mode=PLC, factor=2.0" in line for line in lines)
