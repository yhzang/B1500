"""自定义配方:序列化往返 + 存盘加载 + 坏文件跳过 + 即时注册 + 未存预览。

用椰椰的例子:ERS 4.2V 连写两次 → 延迟 → 读。
"""
from __future__ import annotations

import json

import pytest

from fefetlab.protocols.declared import serialize, user_store
from fefetlab.protocols.declared.schema import (
    DeclaredProtocol,
    DelayStep,
    PulseStep,
    ReadStep,
    ResetStep,
)


def _demo() -> DeclaredProtocol:
    return DeclaredProtocol(
        id="ERS2_DLY", title="ERS 4.2V ×2 → 延迟读",
        steps=(
            ResetStep(t=1e-3),
            PulseStep(v=4.2, width=100e-6),
            PulseStep(v=4.2, width=100e-6),
            DelayStep(t=1e-3),
            ReadStep(vg_list=(-1.0, -0.5), vd=0.05, n_pts=5),
        ),
        states=("ERS",), reps=1,
    )


def test_serialize_roundtrip():
    decl = _demo()
    d = serialize.recipe_to_dict(decl)
    json.dumps(d)                                    # 必须 JSON 可序列化
    back = serialize.recipe_from_dict(d)
    assert back.id == decl.id and back.title == decl.title
    assert len(back.steps) == 5
    assert back.steps[1].kind == "pulse" and back.steps[1].v == 4.2
    assert back.steps[3].kind == "delay" and back.steps[3].t == 1e-3
    assert back.steps[-1].kind == "read" and back.steps[-1].vg_list == (-1.0, -0.5)
    assert back.states == ("ERS",)


def test_store_save_load_delete(tmp_path):
    user_store.save_recipe(_demo(), base=tmp_path)
    loaded = user_store.load_recipes(base=tmp_path)
    assert [d.id for d in loaded] == ["ERS2_DLY"]
    assert user_store.delete_recipe("ERS2_DLY", base=tmp_path) is True
    assert user_store.load_recipes(base=tmp_path) == []


def test_store_bad_json_skipped(tmp_path):
    (tmp_path / "bad.json").write_text("{not valid json", encoding="utf-8")
    user_store.save_recipe(_demo(), base=tmp_path)
    assert [d.id for d in user_store.load_recipes(base=tmp_path)] == ["ERS2_DLY"]


def test_invalid_id_rejected(tmp_path):
    bad = DeclaredProtocol(id="has space!", title="x",
                           steps=(ReadStep(vg_list=(-1.0,), vd=0.05),))
    with pytest.raises(ValueError):
        user_store.save_recipe(bad, base=tmp_path)


def test_register_recipe_live_and_preview():
    from fefetlab.engine import REGISTRY
    from fefetlab.protocols.declared.registry_glue import register_recipe

    from gui.plan_preview import build_timing_preview, preview_declared

    decl = _demo()
    r = preview_declared(decl)                        # 未存先预览(编辑器 path)
    assert r["ok"], r.get("error")
    assert len(r["gate_points"]) >= 2
    assert r["summary"]["n_read_events"] >= 1
    try:
        register_recipe(decl)                         # 即时注册进 REGISTRY
        assert "ERS2_DLY" in REGISTRY
        r2 = build_timing_preview("ERS2_DLY")         # 现在能按 id 预览/跑
        assert r2["ok"], r2.get("error")
    finally:
        REGISTRY.pop("ERS2_DLY", None)                # 清理,免污染 test_engine_run 的全集断言


def test_reserved_builtin_id_and_register_rejected():
    from fefetlab.engine import REGISTRY
    from fefetlab.protocols.declared.registry_glue import is_reserved_builtin_id, register_recipe
    from fefetlab.protocols.declared.schema import DeclaredProtocol, ReadStep

    assert is_reserved_builtin_id("E1S") is True        # 内置 WGFMU
    assert is_reserved_builtin_id("DEMO_RET") is True    # 内置声明式
    assert is_reserved_builtin_id("ZZ_NOPE_123") is False
    bad = DeclaredProtocol(id="E1S", title="HIJACK", steps=(ReadStep(vg_list=(-1.0,), vd=0.05),))
    with pytest.raises(ValueError):
        register_recipe(bad)
    assert REGISTRY["E1S"].family == "WGFMU"             # 没被覆盖


def test_build_declared_user_cannot_override_builtin(monkeypatch):
    import fefetlab.protocols.declared.registry_glue as rg
    from fefetlab.protocols.declared.schema import DeclaredProtocol, ReadStep

    fake = DeclaredProtocol(id="DEMO_RET", title="HIJACK",
                            steps=(ReadStep(vg_list=(-1.0,), vd=0.05),))
    monkeypatch.setattr("fefetlab.protocols.declared.user_store.load_recipes",
                        lambda base=None: [fake])
    specs = rg.build_declared_specs()
    assert specs["DEMO_RET"].title != "HIJACK"           # 内置赢,用户同名不覆盖


def test_unregister_and_custom_ids():
    from fefetlab.engine import REGISTRY
    from fefetlab.protocols.declared.registry_glue import (
        custom_recipe_ids,
        register_recipe,
        unregister_recipe,
    )

    register_recipe(_demo())
    try:
        assert "ERS2_DLY" in custom_recipe_ids()
        assert "E1S" not in custom_recipe_ids()          # 内置不算自定义
        assert "DEMO_RET" not in custom_recipe_ids()     # 内置声明式不算
        assert unregister_recipe("ERS2_DLY") is True
        assert "ERS2_DLY" not in REGISTRY
        assert unregister_recipe("E1S") is False         # 内置不可退注册
        assert REGISTRY["E1S"].family == "WGFMU"
    finally:
        REGISTRY.pop("ERS2_DLY", None)
