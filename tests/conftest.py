"""Pytest configuration: add project root + src to sys.path so tests
can import both ``fefetlab`` (under src/) and ``scripts`` (top-level).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

for p in (str(ROOT), str(SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)
