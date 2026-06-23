"""命名预设(类 EasyEXPERT「My Favorite Setup」):存/取一组参数到 configs/presets/*.json。

预设 = {schema_version, stage, params(SI 口径), identity}。JSON、UTF-8 无 BOM(G 盘铁律)。
纯文件 I/O,零 Qt、零仪器,可单测。文件名做安全清洗(防路径穿越/非法字符)。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SUFFIX = ".json"
_KEEP = "-_.() "


def presets_dir(root: Path | str) -> Path:
    return Path(root) / "configs" / "presets"


def safe_name(name: str) -> str:
    s = "".join(c for c in str(name).strip() if c.isalnum() or c in _KEEP).strip()
    return s or "preset"


def list_presets(root: Path | str) -> list[str]:
    d = presets_dir(root)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*" + _SUFFIX))


def save_preset(root: Path | str, name: str, data: dict) -> Path:
    d = presets_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"schema_version": 1}
    payload.update(data)
    p = d / (safe_name(name) + _SUFFIX)
    # ensure_ascii=False 保中文;encoding utf-8 不带 BOM
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def load_preset(root: Path | str, name: str) -> dict:
    p = presets_dir(root) / (safe_name(name) + _SUFFIX)
    return json.loads(p.read_text(encoding="utf-8"))


def delete_preset(root: Path | str, name: str) -> bool:
    p = presets_dir(root) / (safe_name(name) + _SUFFIX)
    if p.exists():
        p.unlink()
        return True
    return False
