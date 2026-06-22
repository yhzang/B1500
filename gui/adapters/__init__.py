"""存储器适配层(每种存储器一份;壳不改)。

import 各适配模块以触发其 `@register_plot(...)` 把画法登记进
`gui.plot_dispatch.PLOT_DISPATCH`。当前只有 FeFET。
"""
from __future__ import annotations

from . import fefet_plots  # noqa: F401  (import 即注册)

__all__ = ["fefet_plots"]
