"""Pytest configuration.

1) Force the Qt 'offscreen' platform when there is no display (SSH / CI).
   Without this the first QWidget-constructing test aborts the whole process
   with "no Qt platform plugin could be initialized" — which surfaces as a
   phantom exit-9 "segfault". We also defensively strip a trailing space from
   QT_QPA_PLATFORM, because cmd.exe `set VAR=offscreen && ...` leaks the space
   before `&&` into the value (Qt then looks for a plugin named "offscreen ").
2) Add project root + src to sys.path so tests can import both ``fefetlab``
   (under src/) and the top-level ``scripts`` / ``gui`` packages.
3) Provide a session-scoped ``qapp`` fixture so GUI tests do not depend on
   pytest-qt being installed (this overrides pytest-qt's same-named fixture).
"""
import os
import sys
from pathlib import Path

# --- Qt offscreen (headless) -------------------------------------------------
_plat = os.environ.get("QT_QPA_PLATFORM")
if _plat is not None and _plat != _plat.strip():
    os.environ["QT_QPA_PLATFORM"] = _plat.strip()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# --- import paths ------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Session-wide single QApplication. Skips if PySide6 is unavailable.

    Defined here (not via pytest-qt) so the GUI tests run on any machine that
    only has PySide6 installed. A single app for the whole session avoids the
    destruction-order segfaults that come from creating/destroying a
    QApplication per test.
    """
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
