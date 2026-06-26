"""用户自定义配方存盘:每条一个 JSON,默认放 <repo>/recipes/。

GUI 配方编辑器存盘到这里;`build_declared_specs` 加载期把这些一并注册进 REGISTRY,
所以重启也在。坏 JSON 跳过、不拖垮整树。store 目录可注入(测试用 tmp)。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..wgfmu_fefet import ROOT
from .schema import DeclaredProtocol
from .serialize import recipe_from_dict, recipe_to_dict

_ID_OK = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")


def recipes_dir(base: str | Path | None = None) -> Path:
    return Path(base) if base else (ROOT / "recipes")


def is_valid_id(recipe_id: str) -> bool:
    return bool(_ID_OK.match(recipe_id or ""))


def save_recipe(decl: DeclaredProtocol, base: str | Path | None = None) -> Path:
    if not is_valid_id(decl.id):
        raise ValueError(f"配方 id 非法:{decl.id!r}(只允许字母/数字/_/-,≤40)")
    d = recipes_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    fp = d / f"{decl.id}.json"
    fp.write_text(json.dumps(recipe_to_dict(decl), ensure_ascii=False, indent=2),
                  encoding="utf-8")
    return fp


def delete_recipe(recipe_id: str, base: str | Path | None = None) -> bool:
    fp = recipes_dir(base) / f"{recipe_id}.json"
    if fp.exists():
        fp.unlink()
        return True
    return False


def load_recipes(base: str | Path | None = None) -> list[DeclaredProtocol]:
    d = recipes_dir(base)
    out: list[DeclaredProtocol] = []
    if not d.exists():
        return out
    for fp in sorted(d.glob("*.json")):
        try:
            out.append(recipe_from_dict(json.loads(fp.read_text(encoding="utf-8"))))
        except Exception:  # noqa: BLE001  坏文件跳过
            continue
    return out
