"""ParamForm · 按 ProtocolSpec.params 自动生成参数表单(共性壳,与存储器无关)。

设计 §5.4。一个通用渲染器,不为任何协议手写表单——遍历 `spec.params`,按
`ParamSpec.kind`/`visibility` 生成控件,`collect()` 产出可直接并进 RunRequest.params 的 dict。

初版取舍(刻意从简,你后面再改样式):
  * FLOAT/INT/FLOAT_LIST/INT_LIST 一律用 QLineEdit(文本 → collect 时解析)。
    理由:很多参数默认是 None(=用协议标称),且有 1e-6 这种科学计数 + 逗号列表,
    QLineEdit + 解析比 QDoubleSpinBox 配 range/step/decimals 更不容易写错(本机不能跑测)。
  * 列表(FLOAT_LIST/INT_LIST)collect 返回**原始字符串**——因为 run_stage_* 内部是
    `_parse_float_list_csv(args.xxx)` 自己解析字符串的(如 s1_vg/e6d_amps/cycle_checkpoints)。
  * FLOAT/INT 文本为空且默认 None → 返回 None(引擎/runner 回退协议标称值)。
  * Visibility:BASIC 直接显示;ADVANCED 折在"显示高级"开关后;LOCKED 只读灰显 + 🔒。
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from fefetlab.engine.specs import ParamKind, ParamSpec, ProtocolSpec, Visibility


class ParamForm(QWidget):
    """渲染单个协议的参数表单。`set_protocol(spec)` 重建;`collect()` 取值。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fields: list[tuple[ParamSpec, QWidget]] = []
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(6, 6, 6, 6)

        self._basic_box = QGroupBox("基础参数")
        self._basic_form = QFormLayout(self._basic_box)

        self._adv_toggle = QCheckBox("显示高级参数")
        self._adv_toggle.toggled.connect(self._on_adv_toggled)

        self._adv_box = QGroupBox("高级参数")
        self._adv_form = QFormLayout(self._adv_box)
        self._adv_box.setVisible(False)

        self._locked_box = QGroupBox("接线 / 锁定(只读)")
        self._locked_form = QFormLayout(self._locked_box)

        self._empty = QLabel("← 在左侧选择一个协议")
        self._root.addWidget(self._empty)
        self._root.addWidget(self._basic_box)
        self._root.addWidget(self._adv_toggle)
        self._root.addWidget(self._adv_box)
        self._root.addWidget(self._locked_box)
        self._root.addStretch(1)
        self._set_boxes_visible(False)

    # ── 公共 API ────────────────────────────────────────────────────────────
    def set_protocol(self, spec: ProtocolSpec | None) -> None:
        self._clear()
        if spec is None:
            self._empty.setVisible(True)
            self._set_boxes_visible(False)
            return
        self._empty.setVisible(False)
        self._set_boxes_visible(True)
        any_adv = False
        any_locked = False
        for p in spec.params:
            widget = self._make_widget(p)
            self._fields.append((p, widget))
            label = self._label_text(p)
            lbl = QLabel(label)
            if p.help:
                lbl.setToolTip(p.help)
                widget.setToolTip(p.help)
            if p.visibility is Visibility.LOCKED:
                self._locked_form.addRow(lbl, widget)
                any_locked = True
            elif p.visibility is Visibility.ADVANCED:
                self._adv_form.addRow(lbl, widget)
                any_adv = True
            else:
                self._basic_form.addRow(lbl, widget)
        self._adv_toggle.setVisible(any_adv)
        self._adv_box.setVisible(any_adv and self._adv_toggle.isChecked())
        self._locked_box.setVisible(any_locked)

    def collect(self) -> dict[str, Any]:
        """取当前所有字段值。FLOAT/INT 解析失败会抛 ValueError(调用方捕获并提示)。"""
        out: dict[str, Any] = {}
        for p, w in self._fields:
            out[p.name] = self._read_widget(p, w)
        return out

    # ── 内部 ────────────────────────────────────────────────────────────────
    def _make_widget(self, p: ParamSpec) -> QWidget:
        if p.kind is ParamKind.BOOL:
            cb = QCheckBox()
            cb.setChecked(bool(p.default))
            w: QWidget = cb
        elif p.kind is ParamKind.CHOICE:
            combo = QComboBox()
            choices = [str(c) for c in (p.choices or ())]
            combo.addItems(choices)
            if p.default is not None and str(p.default) in choices:
                combo.setCurrentText(str(p.default))
            w = combo
        else:  # FLOAT / INT / FLOAT_LIST / INT_LIST → QLineEdit
            le = QLineEdit()
            if p.default is None:
                le.setPlaceholderText("默认(协议标称)")
            else:
                le.setText(str(p.default))
            w = le
        if p.visibility is Visibility.LOCKED:
            w.setEnabled(False)
            if isinstance(w, QLineEdit):
                w.setReadOnly(True)
        return w

    def _read_widget(self, p: ParamSpec, w: QWidget) -> Any:
        if p.kind is ParamKind.BOOL:
            return bool(w.isChecked())  # type: ignore[attr-defined]
        if p.kind is ParamKind.CHOICE:
            return w.currentText()  # type: ignore[attr-defined]
        text = w.text().strip()  # type: ignore[attr-defined]
        if p.kind in (ParamKind.FLOAT_LIST, ParamKind.INT_LIST):
            # runner 内部自己解析逗号字符串;空串 → runner 回退标称
            return text
        if text == "":
            # 空 → 回退该参数自身默认(默认为 None 才返 None)。避免清空一个有默认值的
            # 数值框后把 None 传进 runner 触发 range(None)/float(None)/None*1e-6 崩。
            return p.default
        if p.kind is ParamKind.INT:
            return int(text)
        return float(text)

    def _label_text(self, p: ParamSpec) -> str:
        base = f"{p.label} ({p.unit})" if p.unit else p.label
        if p.visibility is Visibility.LOCKED:
            return f"🔒 {base}"
        return base

    def _on_adv_toggled(self, checked: bool) -> None:
        self._adv_box.setVisible(checked and self._adv_box_has_rows())

    def _adv_box_has_rows(self) -> bool:
        return self._adv_form.rowCount() > 0

    def _set_boxes_visible(self, visible: bool) -> None:
        self._basic_box.setVisible(visible)
        self._adv_toggle.setVisible(visible)
        self._locked_box.setVisible(visible)
        if not visible:
            self._adv_box.setVisible(False)

    def _clear(self) -> None:
        self._fields.clear()
        for form in (self._basic_form, self._adv_form, self._locked_form):
            while form.rowCount() > 0:
                form.removeRow(0)
