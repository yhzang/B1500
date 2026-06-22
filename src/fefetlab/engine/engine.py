"""ProtocolEngine · 唯一执行门(headless,零 Qt)。

设计文档 §3.3。GUI 与 CLI 都只调这一个 `run`:它把"校验 → 通道映射 → live 门禁 →
驱动协议 runner → 收尾发事件"收口在一处,**任何调用方都绕不过** `validate_live_request`
与安全门。本模块不依赖 Qt,可被 CLI / 测试直接调用。

当前 M1:`run` 已是统一门(校验 + ParamView + 现有 runner + on_stage_done/on_stop_gate/
on_error 事件)。`backend` 由调用方注入(测试给 AuditBackend;CLI/GUI 给 make_backend 结果),
使引擎本身不 import 仪器。会话生命周期封装成 BackendManager、on_shot 接入 runner、
ParamSpec 校验(validate_params) 是 M1 后续步骤(见 §3.5/§3.6)。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, Optional

from ..orchestration.core import StopGate, validate_live_request
from ..protocols.wgfmu_fefet import configure_channel_map
from .callbacks import EngineCallbacks, NullCallbacks
from .param_view import ParamView
from .registry import REGISTRY


class RunMode(Enum):
    DRY = "dry"
    LIVE = "live"


def _is_recoverable(exc: BaseException) -> bool:
    """WGFMU status=-6 类会话退化可 reopen-retry;其余视为致命(见 setup_helpers / FIX B)。"""
    return getattr(exc, "status", None) == -6 or "status=-6" in str(exc)


class ProtocolEngine:
    """唯一执行门。`run` 是 GUI / CLI 共用的入口。"""

    def run(
        self,
        protocol_id: str,
        params: Mapping[str, Any],
        *,
        backend: Any,
        callbacks: Optional[EngineCallbacks] = None,
        confirm: str = "",
    ):
        """跑一个协议(一段)。

        Args:
            protocol_id: REGISTRY 里的协议码,如 "E1" / "E6D"。
            params: 完整参数 dict(CLI 用 vars(args);GUI 用 默认 ∪ 表单值)。含 live/channels。
            backend: 调用方注入的后端(dry=AuditBackend;live=RealWgfmuBackend)。引擎不造后端。
            callbacks: 事件回调;默认 NullCallbacks(runner 内仍 print SHOT_OK/REPORT_CODE)。
            confirm: live 模式必须 == protocol_id,否则 validate_live_request 拦下。

        Returns:
            StageSummary(协议 runner 的返回)。

        Raises:
            KeyError: 未知 protocol_id。
            StopGate: live 门禁未过 / 通道映射非法 / 段内停门。
        """
        if protocol_id not in REGISTRY:
            raise KeyError(f"unknown protocol_id: {protocol_id!r}; known={sorted(REGISTRY)}")
        cb = callbacks or NullCallbacks()
        spec = REGISTRY[protocol_id]
        live = bool(params.get("live", False))
        view = ParamView(params)
        try:
            configure_channel_map(view)                       # 通道映射 + 合法性(gate≠drain/禁用集)
            validate_live_request(protocol_id, live, confirm)  # live 一段一确认,原样复用 core.py
            summary = spec.runner(backend, view, callbacks=cb)  # run_stage_*(backend, view, *, callbacks=None)
            cb.on_stage_done(summary, summary.out_csv.parent)
            return summary
        except StopGate as exc:
            cb.on_stop_gate(exc.code, str(exc), _is_recoverable(exc))
            raise
        except Exception as exc:  # noqa: BLE001 - 引擎门要把任何失败转成事件再上抛
            cb.on_error(exc, _is_recoverable(exc))
            raise
