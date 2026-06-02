from __future__ import annotations

import pytest

from fefetlab.measurements.wgfmu.audit_backend import AuditBackend


def _prepare_minimal_pair(backend: AuditBackend, *, gate_dt: float = 1e-6, drain_dt: float = 1e-6) -> None:
    backend.open_session("DUMMY::WGFMU")
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)
    backend.add_vector("gp", gate_dt, 0.0)
    backend.add_vector("dp", drain_dt, 0.0)
    backend.set_measure_event("gp", "g0", 0.0, 2, 1e-7, 5e-8, "averaged")
    backend.set_measure_event("dp", "d0", 0.0, 2, 1e-7, 5e-8, "averaged")
    backend.add_sequence(301, "gp", 1)
    backend.add_sequence(202, "dp", 1)


def test_audit_backend_is_package_level_and_uses_configurable_gate_drain_channels():
    backend = AuditBackend(gate_ch=301, drain_ch=202, channels=[201, 202, 301, 302])

    _prepare_minimal_pair(backend)
    backend.execute()

    assert backend.get_channel_ids() == [201, 202, 301, 302]
    assert backend.execute_count == 1
    assert backend.max_vectors_seen == 1
    assert backend.get_measure_values(202)["value"].iloc[0] < backend.get_measure_values(301)["value"].iloc[0]


def test_audit_backend_rejects_unsynchronized_gate_and_drain_patterns():
    backend = AuditBackend(gate_ch=301, drain_ch=202)
    _prepare_minimal_pair(backend, gate_dt=1e-6, drain_dt=2e-6)

    with pytest.raises(RuntimeError, match="duration mismatch"):
        backend.execute()


def test_audit_backend_rejects_pattern_vector_budget_overflow():
    backend = AuditBackend(gate_ch=301, drain_ch=202, max_vectors_per_pattern=2)
    backend.open_session("DUMMY::WGFMU")
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)
    for _ in range(3):
        backend.add_vector("gp", 1e-9, 0.0)
        backend.add_vector("dp", 1e-9, 0.0)
    backend.add_sequence(301, "gp", 1)
    backend.add_sequence(202, "dp", 1)

    with pytest.raises(RuntimeError, match="> 2"):
        backend.execute()
