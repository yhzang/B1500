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

    # ── 内部 ────────────────────────────────────────────────────────────────
    def _populate(self) -> None:
        # 按 family 分组(泛化,不硬编码协议码)
        by_family: dict[str, list] = {}
        for spec in REGISTRY.values():
            by_family.setdefault(spec.family, []).append(spec)
        for family in sorted(by_family):
            group = QTreeWidgetItem([family])
            group.setFirstColumnSpanned(True)
            self.tree.addTopLevelItem(group)
            for spec in by_family[family]:
                leaf = QTreeWidgetItem([f"{spec.id}  {spec.title}"])
                leaf.setData(0, _ROLE_ID, spec.id)
                if spec.note:
                    leaf.setToolTip(0, spec.note)
                group.addChild(leaf)
            group.setExpanded(True)

    def _on_item_changed(self, current: QTreeWidgetItem | None, _previous) -> None:
        if current is None:
            return
        pid = current.data(0, _ROLE_ID)
        if not pid:
            return  # 选中的是分组节点
        self._current_id = pid
        self.param_form.set_protocol(REGISTRY[pid])
        self.protocolSelected.emit(pid)
