"""配方编辑器 GUI:骨架可建、校验、预览、保存发信号;菜单入口 + 树活刷新。"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


def test_editor_default_skeleton_builds_valid(qapp):
    from gui.recipe_editor import RecipeEditorDialog

    dlg = RecipeEditorDialog()
    dlg._id.setText("MY_TEST")
    decl = dlg._build_decl()
    assert decl.id == "MY_TEST"
    assert [s.kind for s in decl.steps] == ["reset", "pulse", "delay", "read"]
    assert dlg._validate(decl) is None                      # 骨架合法


def test_editor_validate_rejects(qapp):
    from gui.recipe_editor import RecipeEditorDialog

    dlg = RecipeEditorDialog()
    dlg._id.setText("bad id!")
    assert dlg._validate(dlg._build_decl()) is not None     # 非法 id
    dlg._id.setText("OK_ID")
    while dlg._tbl.rowCount() and dlg._tbl.item(dlg._tbl.rowCount() - 1, 0).text() == "读":
        dlg._tbl.removeRow(dlg._tbl.rowCount() - 1)
    assert "读" in (dlg._validate(dlg._build_decl()) or "")  # 末尾非读


def test_editor_preview_works(qapp):
    pytest.importorskip("pyqtgraph")
    from gui.plan_preview import preview_declared
    from gui.recipe_editor import RecipeEditorDialog

    dlg = RecipeEditorDialog()
    dlg._id.setText("PREV_TEST")
    r = preview_declared(dlg._build_decl())
    assert r["ok"], r.get("error")
    assert len(r["gate_points"]) >= 2


def test_editor_save_emits(qapp, monkeypatch):
    from gui.recipe_editor import RecipeEditorDialog

    dlg = RecipeEditorDialog()
    dlg._id.setText("SAVE_TEST")
    got: list = []
    dlg.saved.connect(got.append)
    monkeypatch.setattr("fefetlab.protocols.declared.user_store.save_recipe",
                        lambda decl, base=None: None)
    monkeypatch.setattr("fefetlab.protocols.declared.registry_glue.register_recipe",
                        lambda decl: None)
    dlg._on_save()
    assert got == ["SAVE_TEST"]


def test_mainwindow_new_recipe_menu(qapp):
    from gui.app import MainWindow

    win = MainWindow()
    labels: list = []
    for act in win.menuBar().actions():
        m = act.menu()
        if m:
            labels += [a.text() for a in m.actions()]
    assert any("自定义协议" in t for t in labels)


def test_recipe_saved_refreshes_tree(qapp):
    from fefetlab.engine import REGISTRY
    from fefetlab.protocols.declared.registry_glue import register_recipe
    from fefetlab.protocols.declared.schema import DeclaredProtocol, ReadStep

    from gui.app import MainWindow

    win = MainWindow()
    decl = DeclaredProtocol(id="TREE_TEST", title="树测试",
                            steps=(ReadStep(vg_list=(-1.0,), vd=0.05),), states=("ERS",))
    try:
        register_recipe(decl)
        win._on_recipe_saved("TREE_TEST")
        assert win.protocol_panel.select_protocol("TREE_TEST")   # 树里出现且可选中
    finally:
        REGISTRY.pop("TREE_TEST", None)
        win.protocol_panel.refresh()


def test_editor_build_decl_bad_vg_raises(qapp):
    from gui.recipe_editor import RecipeEditorDialog

    dlg = RecipeEditorDialog()
    last = dlg._tbl.rowCount() - 1
    dlg._tbl.item(last, 4).setText("-1.0,abc")           # 读 Vg 含字母
    with pytest.raises(ValueError):
        dlg._build_decl()


def test_editor_validate_negative_width(qapp):
    from gui.recipe_editor import RecipeEditorDialog

    dlg = RecipeEditorDialog()
    dlg._id.setText("OK_ID")
    for r in range(dlg._tbl.rowCount()):
        if dlg._tbl.item(r, 0).text() == "脉冲":
            dlg._tbl.item(r, 2).setText("-1e-6")
    assert "宽度" in (dlg._validate(dlg._build_decl()) or "")


def test_editor_save_reserved_id_blocked(qapp, monkeypatch):
    from gui.recipe_editor import RecipeEditorDialog

    dlg = RecipeEditorDialog()
    dlg._id.setText("E1S")                               # 内置 id
    got: list = []
    dlg.saved.connect(got.append)
    monkeypatch.setattr("gui.recipe_editor.QMessageBox.warning", lambda *a, **k: None)
    dlg._on_save()
    assert got == []                                     # 被拦,没保存


def test_mainwindow_delete_recipe_menu(qapp):
    from gui.app import MainWindow

    win = MainWindow()
    labels: list = []
    for act in win.menuBar().actions():
        m = act.menu()
        if m:
            labels += [a.text() for a in m.actions()]
    assert any("删除自定义协议" in t for t in labels)


def test_protocol_panel_new_recipe_button(qapp):
    from gui.protocol_panel import ProtocolPanel

    p = ProtocolPanel()
    assert hasattr(p, "btn_new_recipe")          # 协议树下方有显眼的"新建自定义协议"按钮
    fired: list = []
    p.newRecipeRequested.connect(lambda: fired.append(1))
    p.btn_new_recipe.click()
    assert fired == [1]                           # 点击发信号(壳接到开编辑器)
