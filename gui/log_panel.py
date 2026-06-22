"""LogPanel · 结构化日志(分级着色 + 过滤)(共性壳)。

来源:引擎事件 on_log(level, code, msg) 以及 worker 翻译的 stageDone/stopGate/error。
初版:只读 QPlainTextEdit + 四级过滤;颜色 INFO 灰 / WARN 橙 / STOP 红粗 / ERROR 红底。
落盘到 run_log.txt 留待迭代(设计 §6.4)。
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

_LEVELS = ("INFO", "WARN", "STOP", "ERROR")
_COLOR = {
    "INFO": QColor("#666666"),
    "WARN": QColor("#C07000"),
    "STOP": QColor("#B80000"),
    "ERROR": QColor("#B80000"),
}


class LogPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[tuple[str, str]] = []  # (level, text)
        self._filters: dict[str, QCheckBox] = {}

        filt_lay = QHBoxLayout()
        for lv in _LEVELS:
            cb = QCheckBox(lv)
            cb.setChecked(True)
            cb.toggled.connect(self._refilter)
            self._filters[lv] = cb
            filt_lay.addWidget(cb)
        filt_lay.addStretch(1)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(5000)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(filt_lay)
        lay.addWidget(self.view)

    def append(self, level: str, code: str, msg: str) -> None:
        level = (level or "INFO").upper()
        if level not in _LEVELS:
            level = "INFO"
        text = f"[{level}] {code}: {msg}" if code else f"[{level}] {msg}"
        self._entries.append((level, text))
        if self._filters[level].isChecked():
            self._write_line(level, text)

    def clear(self) -> None:
        self._entries.clear()
        self.view.clear()

    def export_text(self) -> str:
        """导出当前全部日志缓冲(不受过滤影响),供 run_log.txt 落盘。"""
        return "\n".join(text for _level, text in self._entries)

    # ── 内部 ────────────────────────────────────────────────────────────────
    def _write_line(self, level: str, text: str) -> None:
        cursor = self.view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(_COLOR.get(level, _COLOR["INFO"]))
        if level in ("STOP", "ERROR"):
            font = fmt.font()
            font.setBold(True)
            fmt.setFont(font)
        cursor.insertText(text + "\n", fmt)
        self.view.setTextCursor(cursor)
        self.view.ensureCursorVisible()

    def _refilter(self) -> None:
        self.view.clear()
        for level, text in self._entries:
            if self._filters[level].isChecked():
                self._write_line(level, text)
