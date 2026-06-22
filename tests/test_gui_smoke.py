"""GUI 初版离屏冒烟测试(在测试机跑;无 PySide6 自动 skip)。

只做"构造不抛 + ParamForm 覆盖每个协议每个 ParamSpec",不起事件循环、不跑引擎、不碰硬件。
真正的端到端 dry 跑通由 test_engine_run / test_cli_dry_golden 守(引擎层),GUI 这里只验装配。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 让 `import gui`(顶层包,不随 fefetlab 安装)可被找到
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from fefetlab.engine import REGISTRY  # noqa: E402

from gui.param_form import ParamForm  # noqa: E402


_APP = None  # 模块全局持有:否则测试结束 QApplication/widget 被 GC、析构顺序错乱会段错误(pytest-qt 经典坑)


def _ensure_app() -> QApplication:
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


def test_param_form_covers_every_protocol_param():
    _ensure_app()
    form = ParamForm()
    for _pid, spec in REGISTRY.items():
        form.set_protocol(spec)
        out = form.collect()
        for p in spec.params:
            assert p.name in out, f"{spec.id} 缺字段 {p.name}"


def test_mainwindow_constructs():
    _ensure_app()
    from gui.app import MainWindow

    win = MainWindow()
    assert win.protocol_panel is not None
    assert win.controller is not None
