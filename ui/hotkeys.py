"""热键设置窗口"""
import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QComboBox, QPushButton, QFrame)
from PySide6.QtCore import Qt

# 可用的功能键
KEY_NAMES = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
}
KEY_LABELS = {v: k for k, v in KEY_NAMES.items()}

DEFAULT_KEYS = {
    "小窗查看": 0x76,   # F7
    "截图": 0x77,        # F8
    "预览效果": 0x78,    # F9
    "自动钓鱼": 0x79,    # F10
    "参数调整": 0x7B,    # F12
}


class HotkeyWindow:
    def __init__(self, on_change=None):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self._on_change = on_change
        self._visible = False
        self._keymap = dict(DEFAULT_KEYS)
        self._create()

    def _create(self):
        self.win = QWidget()
        self.win.setWindowTitle("热键设置")
        self.win.setFixedSize(300, 220)
        self.win.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)

        layout = QVBoxLayout(self.win)

        title = QLabel("快捷键设置")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)
        layout.addWidget(QFrame().setFrameShape(QFrame.HLine) or QFrame())

        self._combos = {}
        for action, vk in DEFAULT_KEYS.items():
            row = QHBoxLayout()
            label = QLabel(action)
            label.setFixedWidth(70)
            row.addWidget(label)

            combo = QComboBox()
            combo.addItems(KEY_NAMES.keys())
            combo.setCurrentText(KEY_LABELS.get(vk, "F7"))
            combo.currentTextChanged.connect(lambda t, a=action: self._on_combo(a, t))
            row.addWidget(combo)
            self._combos[action] = combo
            layout.addLayout(row)

        layout.addStretch()

    def _on_combo(self, action, text):
        if text in KEY_NAMES:
            old = self._keymap.get(action)
            new = KEY_NAMES[text]
            # check conflicts
            for a, v in self._keymap.items():
                if a != action and v == new:
                    self._combos[action].setCurrentText(KEY_LABELS.get(old, ""))
                    return
            self._keymap[action] = new
            if self._on_change:
                self._on_change(action, new)

    def get_keys(self):
        return dict(self._keymap)

    def toggle(self):
        self._visible = not self._visible
        if self._visible:
            self.win.show()
        else:
            self.win.hide()

    def close(self):
        self.win.hide()
        self.app.processEvents()
