"""自定义配方编辑器:在界面里拼 复位/脉冲/延迟/读 步骤,预览 + 保存为自定义协议。

保存 = 写 JSON 到 recipes/ + 即时注册进 REGISTRY(emit saved(id),壳刷新树),免重启。
自由度:任意条脉冲(含符号 = 极性)、任意段间延迟(DelayStep,硬件计时、可设 0)、末尾读。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_TYPES = ("复位", "脉冲", "延迟", "读")
_COLS = ["类型", "电压 v (V)", "宽度/时长 (s)", "按态取号", "读 Vg (逗号)", "读 Vd (V)", "n_pts"]
_STATES = {"双极(ERS+PGM)": ("ERS", "PGM"), "仅 ERS": ("ERS",), "仅 PGM": ("PGM",)}
_DEFAULTS = {
    "复位": {2: "1e-3"},
    "脉冲": {1: "4.0", 2: "100e-6", 3: "否"},
    "延迟": {2: "1e-3"},
    "读": {4: "-1.0,-0.5", 5: "0.05", 6: "5"},
}


def _f(item, default: float) -> float:
    try:
        return float(item.text())
    except (AttributeError, ValueError):
        return default


class RecipeEditorDialog(QDialog):
    saved = Signal(str)   # 保存成功后发新协议 id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建自定义协议(配方编辑器)")
        self.resize(740, 580)
        lay = QVBoxLayout(self)

        head = QFormLayout()
        self._id = QLineEdit()
        self._id.setPlaceholderText("协议码(字母/数字/_/-,如 MY_ERS2)")
        self._title = QLineEdit()
        self._title.setPlaceholderText("形象名(树里显示,如 ERS 4.2V ×2 延迟读)")
        self._states = QComboBox()
        self._states.addItems(_STATES.keys())
        self._reps = QSpinBox()
        self._reps.setRange(1, 9999)
        head.addRow("协议码 id", self._id)
        head.addRow("形象名", self._title)
        head.addRow("写态", self._states)
        head.addRow("重复次数", self._reps)
        lay.addLayout(head)

        self._tbl = QTableWidget(0, len(_COLS))
        self._tbl.setHorizontalHeaderLabels(_COLS)
        self._tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lay.addWidget(self._tbl, 1)

        addrow = QHBoxLayout()
        for t in _TYPES:
            b = QPushButton(f"加{t}")
            b.clicked.connect(lambda _=False, tt=t: self._add_step(tt))
            addrow.addWidget(b)
        addrow.addStretch(1)
        for txt, fn in (("上移", self._move_up), ("下移", self._move_down), ("删除", self._del_row)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            addrow.addWidget(b)
        lay.addLayout(addrow)

        hint = QLabel("步骤从上到下执行,**末尾必须是「读」**。延迟 = 段间停顿(栅0漏0,硬件计时,可设 0)。"
                      "脉冲电压含符号(ERS 用正、PGM 用负);勾「按态取号」(填「是」)则幅值按写态自动取号。")
        hint.setStyleSheet("color:#888;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btns = QHBoxLayout()
        b_prev = QPushButton("预览时序")
        b_prev.clicked.connect(self._on_preview)
        b_save = QPushButton("保存")
        b_save.clicked.connect(self._on_save)
        b_cancel = QPushButton("取消")
        b_cancel.clicked.connect(self.reject)
        btns.addWidget(b_prev)
        btns.addStretch(1)
        btns.addWidget(b_save)
        btns.addWidget(b_cancel)
        lay.addLayout(btns)

        for t in _TYPES:                                  # 起手给常见骨架:复位→脉冲→延迟→读
            self._add_step(t)

    # ── 步骤表 ──────────────────────────────────────────────────────────────
    def _add_step(self, typ: str) -> None:
        r = self._tbl.rowCount()
        self._tbl.insertRow(r)
        it = QTableWidgetItem(typ)
        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._tbl.setItem(r, 0, it)
        for c in range(1, len(_COLS)):
            self._tbl.setItem(r, c, QTableWidgetItem(_DEFAULTS[typ].get(c, "")))

    def _sel_row(self) -> int:
        rows = self._tbl.selectionModel().selectedRows()
        return rows[0].row() if rows else self._tbl.currentRow()

    def _del_row(self) -> None:
        r = self._sel_row()
        if r >= 0:
            self._tbl.removeRow(r)

    def _move_up(self) -> None:
        r = self._sel_row()
        if r > 0:
            self._swap(r, r - 1)
            self._tbl.selectRow(r - 1)

    def _move_down(self) -> None:
        r = self._sel_row()
        if 0 <= r < self._tbl.rowCount() - 1:
            self._swap(r, r + 1)
            self._tbl.selectRow(r + 1)

    def _swap(self, a: int, b: int) -> None:
        for c in range(len(_COLS)):
            ta, tb = self._tbl.takeItem(a, c), self._tbl.takeItem(b, c)
            self._tbl.setItem(a, c, tb)
            self._tbl.setItem(b, c, ta)

    # ── 组装 / 校验 ──────────────────────────────────────────────────────────
    def _build_decl(self):
        from fefetlab.protocols.declared.schema import (
            DeclaredProtocol,
            DelayStep,
            PulseStep,
            ReadStep,
            ResetStep,
        )

        steps = []
        for r in range(self._tbl.rowCount()):
            typ = self._tbl.item(r, 0).text()
            if typ == "复位":
                steps.append(ResetStep(t=_f(self._tbl.item(r, 2), 1e-3)))
            elif typ == "脉冲":
                sign = (self._tbl.item(r, 3).text().strip() in ("是", "y", "Y", "1", "true", "True"))
                steps.append(PulseStep(v=_f(self._tbl.item(r, 1), 0.0),
                                       width=_f(self._tbl.item(r, 2), 100e-6), sign_by_state=sign))
            elif typ == "延迟":
                steps.append(DelayStep(t=_f(self._tbl.item(r, 2), 0.0)))
            elif typ == "读":
                vg_txt = self._tbl.item(r, 4).text().replace("，", ",")
                vg = tuple(float(x) for x in vg_txt.split(",") if x.strip())
                steps.append(ReadStep(vg_list=vg or (-1.0,),
                                      vd=_f(self._tbl.item(r, 5), 0.05),
                                      n_pts=int(_f(self._tbl.item(r, 6), 5))))
        return DeclaredProtocol(
            id=self._id.text().strip(),
            title=self._title.text().strip() or self._id.text().strip(),
            steps=tuple(steps),
            states=_STATES[self._states.currentText()],
            reps=self._reps.value(),
        )

    def _validate(self, decl) -> str | None:
        from fefetlab.protocols.declared.user_store import is_valid_id
        if not is_valid_id(decl.id):
            return "协议码非法(只允许字母/数字/_/-,≤40,不能空)"
        if not decl.steps or decl.steps[-1].kind != "read":
            return "末尾必须是「读」步骤"
        return None

    # ── 预览 / 保存 ──────────────────────────────────────────────────────────
    def _on_preview(self) -> None:
        decl = self._build_decl()
        msg = self._validate(decl)
        if msg:
            QMessageBox.warning(self, "无法预览", msg)
            return
        from .plan_preview import preview_declared
        from .timing_preview_dialog import TimingPreviewDialog

        r = preview_declared(decl)
        if not r.get("ok"):
            QMessageBox.warning(self, "预览失败", str(r.get("error")))
            return
        TimingPreviewDialog(r, self).exec()

    def _on_save(self) -> None:
        decl = self._build_decl()
        msg = self._validate(decl)
        if msg:
            QMessageBox.warning(self, "无法保存", msg)
            return
        from fefetlab.engine import REGISTRY
        if decl.id in REGISTRY and REGISTRY[decl.id].family != "CUSTOM":
            QMessageBox.warning(self, "ID 冲突", f"{decl.id} 与内置协议重名,换一个")
            return
        from fefetlab.protocols.declared.registry_glue import register_recipe
        from fefetlab.protocols.declared.user_store import save_recipe
        try:
            save_recipe(decl)
            register_recipe(decl)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        self.saved.emit(decl.id)
        self.accept()
