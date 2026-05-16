import builtins
import importlib
import sys


def _purge_modules(prefix: str) -> None:
    for name in list(sys.modules):
        if name == prefix or name.startswith(f"{prefix}."):
            sys.modules.pop(name, None)


def test_package_root_does_not_import_visa_session_eagerly():
    _purge_modules("fefetlab")

    importlib.import_module("fefetlab")

    assert "fefetlab.instruments.visa_session" not in sys.modules


def test_import_dc_module_without_pyvisa(monkeypatch):
    _purge_modules("fefetlab")
    _purge_modules("pyvisa")

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pyvisa":
            raise ModuleNotFoundError("No module named 'pyvisa'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    dc_module = importlib.import_module("fefetlab.measurements.dc")

    assert dc_module is not None
    assert dc_module.DCMeasurePoint is not None


def test_visa_session_query_returns_instrument_response():
    _purge_modules("fefetlab")

    visa_session = importlib.import_module("fefetlab.instruments.visa_session")

    class FakeInstrument:
        def query(self, cmd: str) -> str:
            assert cmd == "*IDN?"
            return "FAKE,B1500,0,1"

    session = visa_session.VisaSession(visa_session.VisaConfig(resource="FAKE::INSTR"))
    session.inst = FakeInstrument()

    assert session.query("*IDN?") == "FAKE,B1500,0,1"
