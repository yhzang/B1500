"""ProtocolPanel · 协议树(按 family 泛化分组)+ 托管 ParamForm(共性壳)。

树节点来源 = `REGISTRY` 按 `ProtocolSpec.family` 分组,**不写死任何具体协议码**。
现在只有 WGFMU 一族;将来注册了别的 family,这里自动多出一组,壳不改。
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from fefetlab.engine import REGISTRY

from .param_form import ParamForm

_ROLE_ID = Qt.ItemDataRole.UserRole


class ProtocolPanel(QWidget):
    """左栏:上=协议树,下=该协议的参数表单。"""

    protocolSelected = Signal(str)  # protocol_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_id: str | None = None

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.currentItemChanged.connect(self._on_item_changed)

        self.param_form = ParamForm()
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(self.param_form)

        splitter = QSplitter(Qt.Orientation.Vertical)
        top = QWidget()
        top_lay = QVBoxLayout(top)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.addWidget(QLabel("协议(按设备族分组)"))
        top_lay.addWidget(self.tree)
        splitter.addWidget(top)
        splitter.addWidget(form_scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(splitter)

        self._populate()

    # ── 公共 API ────────────────────────────────────────────────────────────
    def current_protocol_id(self) -> str | None:
        return self._current_id

    def collect_params(self) -> dict:
        return self.param_form.collect()

    def select_protocol(self, pid: str) -> bool:
        """按 id 选中协议(触发 set_protocol + protocolSelected),供预设加载用。"""
        for i in range(self.tree.topLevelItemCount()):
            grp = self.tree.topLevelItem(i)
            for j in range(grp.childCount()):
                ch = grp.child(j)
                if ch.data(0, _ROLE_ID) == pid:
                    self.tree.setCurrentItem(ch)
                    return True
        return False

    # ── 内部 ────────────────────────────────────────────────────────────────
    def _populate(self) -> None:
        # 按 group(按"测什么")分组,first-occurrence 顺序(=协议工作流顺序);group 空回退 family。
        # 叶子显示"形象名(代号)";tooltip 给完整说明。仍不硬编码任何协议码。
        by_group: dict[str, list] = {}
        order: list[str] = []
        for spec in REGISTRY.values():
            key = spec.group or spec.family
            if key not in by_group:
                by_group[key] = []
                order.append(key)
            by_group[key].append(spec)
        for key in order:
            grp = QTreeWidgetItem([key])
            grp.setFirstColumnSpanned(True)
            self.tree.addTopLevelItem(grp)
            for spec in by_group[key]:
                leaf = QTreeWidgetItem([f"{spec.title}  ({spec.id})"])
                leaf.setData(0, _ROLE_ID, spec.id)
                tip = spec.note or spec.description or ""
                if tip:
                    leaf.setToolTip(0, tip)
                grp.addChild(leaf)
            grp.setExpanded(True)

    def _on_item_changed(self, current: QTreeWidgetItem | None, _previous) -> None:
        if current is None:
            return
        pid = current.data(0, _ROLE_ID)
        if not pid:
            return  # 选中的是分组节点
        self._current_id = pid
        self.param_form.set_protocol(REGISTRY[pid])
        self.protocolSelected.emit(pid)
