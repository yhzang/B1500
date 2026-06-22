"""ParamForm · 按 ProtocolSpec.params 自动生成参数表单(共性壳,与存储器无关)。

设计 §5.4。一个通用渲染器,不为任何协议手写表单——遍历 `spec.params`,按
`ParamSpec.kind`/`widget`/`visibility` 生成 typed 控件,`collect()` 产出可直接并进
RunRequest.params 的 dict(SI 口径,与 CLI argparse 默认同单位)。

增量2(2026-06-22)起:按 widget/kind 渲染 typed 控件,而非清一色 QLineEdit。
  * INT(有具体默认)            → QSpinBox(套 minimum/maximum;reps 下限1)
  * FLOAT(有具体默认)          → QDoubleSpinBox(+ 单位后缀;时间单位 µs/ns/ms 做 SI 缩放)
  * CHOICE / 带 choices 的 COMBO → QComboBox
  * BOOL                         → QCheckBox
  * FLOAT_LIST / INT_LIST        → QLineEdit(逗号分隔,带格式校验 + 非法红框)
  * LOCKED(接线/铁律)          → 只读显示,collect 原样返默认(不可改)
  * 默认 None 的数值(=用协议标称)→ 仍保留可空 QLineEdit,空 → None(runner 回退标称)

**SI 缩放只对时间单位 µs/ns/ms**(它们的默认值以「秒」存,显示成工程量):collect 时乘回因子
还原秒。`µA/nA` 不缩放——本仓库 `*_uA` 参数的默认值本就以 µA 存(runner 内部再 ×1e-6),
缩放会双重换算。`s/V/A/Hz` 不缩放。
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fefetlab.engine.specs import ParamKind, ParamSpec, ProtocolSpec, Visibility, Widget

# 仅时间单位做 SI 工程量缩放(默认值以秒存):显示工程量、collect 乘回因子还原秒。
# µA/nA 不在此——本仓库 *_uA 默认值本就以 µA 存(runner 再 ×1e-6),缩放会双重换算。
_SI_FACTOR = {"µs": 1e-6, "μs": 1e-6, "us": 1e-6, "ns": 1e-9, "ms": 1e-3}
_INVALID_QSS = "border: 1px solid #B80000; background: #FFF0F0;"
_LIST_KINDS = (ParamKind.FLOAT_LIST, ParamKind.INT_LIST)


def _si_factor(unit: str) -> float:
    return _SI_FACTOR.get(unit or "", 1.0)


def _default_str(p: ParamSpec) -> str:
    return "" if p.default is None else str(p.default)


class ParamForm(QWidget):
    """渲染单个协议的参数表单。`set_protocol(spec)` 重建;`collect()` 取值;`is_valid()` 校验。"""

    validityChanged = Signal(bool)  # 文本字段格式合法性变化(app 可据此禁用运行)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fields: list[tuple[ParamSpec, QWidget]] = []
        self._invalid: set[str] = set()
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
            lbl = QLabel(self._label_text(p))
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
        self.validityChanged.emit(self.is_valid())

    def collect(self) -> dict[str, Any]:
        """取当前所有字段值(SI 口径)。文本字段解析失败抛 ValueError(调用方捕获并提示)。"""
        out: dict[str, Any] = {}
        for p, w in self._fields:
            out[p.name] = self._read_widget(p, w)
        return out

    def is_valid(self) -> bool:
        """所有自由文本字段格式合法(空=用默认,算合法)。typed 控件天然合法。"""
        return not self._invalid

    # ── 控件构造 ──────────────────────────────────────────────────────────────
    def _make_widget(self, p: ParamSpec) -> QWidget:
        # LOCKED(接线/铁律):只读显示,不可改
        if p.visibility is Visibility.LOCKED:
            le = QLineEdit(_default_str(p))
            le.setReadOnly(True)
            le.setEnabled(False)
            return le
        if p.kind is ParamKind.BOOL:
            cb = QCheckBox()
            cb.setChecked(bool(p.default))
            return cb
        if p.choices:  # CHOICE 或 带 choices 的 COMBO
            combo = QComboBox()
            choices = [str(c) for c in p.choices]
            combo.addItems(choices)
            if p.default is not None and str(p.default) in choices:
                combo.setCurrentText(str(p.default))
            return combo
        if p.kind in _LIST_KINDS:  # 逗号分隔列表 → 带校验的 QLineEdit
            return self._list_lineedit(p)
        if p.kind is ParamKind.INT:
            if p.default is None:
                return self._nullable_lineedit(p)
            sb = QSpinBox()
            sb.setRange(int(p.minimum) if p.minimum is not None else 0,
                        int(p.maximum) if p.maximum is not None else 2_000_000_000)
            sb.setValue(int(p.default))
            return sb
        if p.kind is ParamKind.FLOAT:
            if p.default is None:
                return self._nullable_lineedit(p)
            f = _si_factor(p.unit)
            dsb = QDoubleSpinBox()
            dsb.setDecimals(6)
            dsb.setSingleStep(0.1)
            lo = (p.minimum / f) if p.minimum is not None else -1e12
            hi = (p.maximum / f) if p.maximum is not None else 1e12
            dsb.setRange(lo, hi)
            dsb.setValue(float(p.default) / f)
            if p.unit:
                dsb.setSuffix(f" {p.unit}")
            dsb.setProperty("si_factor", f)
            return dsb
        # 兜底:可空文本
        return self._nullable_lineedit(p)

    def _nullable_lineedit(self, p: ParamSpec) -> QLineEdit:
        """默认 None 的数值:可留空 → collect 返 None(runner 回退协议标称)。"""
        le = QLineEdit()
        if p.default is None:
            le.setPlaceholderText("默认(协议标称)")
        else:
            le.setText(str(p.default))
        le.textChanged.connect(lambda _t, pp=p, ww=le: self._on_text_changed(pp, ww))
        return le

    def _list_lineedit(self, p: ParamSpec) -> QLineEdit:
        le = QLineEdit()
        if p.default is None:
            le.setPlaceholderText("逗号分隔(留空=协议标称)")
        else:
            le.setText(str(p.default))
        le.textChanged.connect(lambda _t, pp=p, ww=le: self._on_text_changed(pp, ww))
        return le

    # ── 取值 ──────────────────────────────────────────────────────────────────
    def _read_widget(self, p: ParamSpec, w: QWidget) -> Any:
        if p.visibility is Visibility.LOCKED:
            return p.default
        if isinstance(w, QCheckBox):
            return bool(w.isChecked())
        if isinstance(w, QComboBox):
            return w.currentText()
        if isinstance(w, QSpinBox):
            return int(w.value())
        if isinstance(w, QDoubleSpinBox):
            f = float(w.property("si_factor") or 1.0)
            return float(w.value()) * f
        # QLineEdit:列表返原始字符串(runner 自解析);数值空→默认(None),否则解析
        text = w.text().strip()
        if p.kind in _LIST_KINDS:
            self._check_list(p, text)  # 非法抛 ValueError
            return text
        if text == "":
            return p.default
        if p.kind is ParamKind.INT:
            return int(text)
        return float(text)

    # ── 校验 ──────────────────────────────────────────────────────────────────
    def _on_text_changed(self, p: ParamSpec, w: QLineEdit) -> None:
        ok = self._field_ok(p, w.text().strip())
        w.setStyleSheet("" if ok else _INVALID_QSS)
        (self._invalid.discard if ok else self._invalid.add)(p.name)
        self.validityChanged.emit(self.is_valid())

    def _field_ok(self, p: ParamSpec, text: str) -> bool:
        if text == "":
            return True  # 空 = 用默认/标称,合法
        try:
            if p.kind in _LIST_KINDS:
                self._check_list(p, text)
            elif p.kind is ParamKind.INT:
                int(text)
            else:
                float(text)
            return True
        except ValueError:
            return False

    @staticmethod
    def _check_list(p: ParamSpec, text: str) -> None:
        if text == "":
            return
        cast = int if p.kind is ParamKind.INT_LIST else float
        for part in text.split(","):
            part = part.strip()
            if part:
                cast(part)  # 非法 → ValueError

    # ── 杂项 ──────────────────────────────────────────────────────────────────
    def _label_text(self, p: ParamSpec) -> str:
        base = f"{p.label} ({p.unit})" if p.unit else p.label
        return f"🔒 {base}" if p.visibility is Visibility.LOCKED else base

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
        self._invalid.clear()
        for form in (self._basic_form, self._adv_form, self._locked_form):
            while form.rowCount() > 0:
                form.removeRow(0)
