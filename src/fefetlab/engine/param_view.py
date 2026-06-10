"""ParamView · 让 run_stage_*(backend, args) 脱离 argparse 而函数体零改动。

设计文档 §3.4。现有 11 个 `run_stage_*` 内部到处是 `args.e1_reps` / `args.device_id` /
`_resolve_write_v(state, args)` / `_build_manifest(args, ...)`。最低风险的收口做法**不是**
改这些函数体,而是给它们一个 dict 后端的只读命名空间替身,让所有 `getattr(args, ...)` 照常命中。
这样 GUI / CLI / 测试都能用同一套参数 dict 驱动同一批协议逻辑。

吸收评审 C3:草稿的 `__getattr__` 直接 `return self._d[k]` 会在 `_d` 未就绪时无限递归。
修正:`_d` 用 `object.__setattr__` 写入,`__getattr__` 用 `object.__getattribute__` 取 `_d`,
并对 `_d` 自身短路。
"""
from __future__ import annotations

from typing import Any, Mapping


class ParamView:
    """包裹一个完整参数 dict,对外表现得像 argparse 的 Namespace(支持 args.x 读、可写)。

    用法::

        view = ParamView(vars(parse_args(argv)))     # CLI
        view = ParamView({**defaults, **form_values}) # GUI(后续)
        run_stage_e1(backend, view)                   # 现有函数一行不改

    `getattr(view, "write_v", None)` 这类带默认的读法也成立(缺键 → AttributeError → 取默认)。
    """

    def __init__(self, params: Mapping[str, Any]):
        object.__setattr__(self, "_d", dict(params))

    def __getattr__(self, name: str) -> Any:
        if name == "_d":  # 短路,避免 _d 未就绪时递归
            raise AttributeError(name)
        d = object.__getattribute__(self, "_d")
        try:
            return d[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        object.__getattribute__(self, "_d")[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        return object.__getattribute__(self, "_d").get(name, default)

    def as_dict(self) -> dict:
        return dict(object.__getattribute__(self, "_d"))
