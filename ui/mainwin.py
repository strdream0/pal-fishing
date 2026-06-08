"""主控制窗口"""
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget,
                                QVBoxLayout, QPushButton, QLabel, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont


class MainWindow(QMainWindow):
    closed = None  # signal, set from outside

    def __init__(self, toggle_preview, toggle_result, toggle_params,
                 toggle_hotkeys, toggle_auto=None):
        super().__init__()
        self._shutdown_cb = None
        self.setWindowTitle("帕鲁钓鱼")
        self.setFixedSize(240, 260)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        try:
            self.setWindowIcon(QIcon("fish.ico"))
        except Exception:
            pass

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)

        title = QLabel("帕鲁钓鱼助手")
        title.setFont(QFont("Microsoft YaHei", 11))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        link = QLabel('<a href="https://github.com/strdream0/pal-fishing">github.com/strdream0/pal-fishing</a>')
        link.setAlignment(Qt.AlignCenter)
        link.setOpenExternalLinks(True)
        link.setStyleSheet("font-size: 9px;")
        layout.addWidget(link)

        qq = QLabel("QQ群: 162714267")
        qq.setAlignment(Qt.AlignCenter)
        qq.setStyleSheet("font-size: 9px; color: gray;")
        layout.addWidget(qq)

        layout.addWidget(self._hr())

        self._status_label = QLabel("状态: 运行中")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setStyleSheet("color: #0f0;")
        layout.addWidget(self._status_label)
        layout.addWidget(self._hr())

        self._btn_preview = QPushButton("预览效果 [F9]")
        self._btn_preview.clicked.connect(toggle_preview)
        layout.addWidget(self._btn_preview)

        self._btn_result = QPushButton("小窗查看 [F7]")
        self._btn_result.clicked.connect(toggle_result)
        layout.addWidget(self._btn_result)

        self._btn_params = QPushButton("参数调整 [F12]")
        self._btn_params.clicked.connect(toggle_params)
        layout.addWidget(self._btn_params)

        self._btn_hotkeys = QPushButton("热键设置")
        self._btn_hotkeys.clicked.connect(toggle_hotkeys)
        layout.addWidget(self._btn_hotkeys)

        layout.addWidget(self._hr())

        self._btn_auto = QPushButton("开启自动钓鱼 [F10]")
        self._btn_auto.clicked.connect(toggle_auto or (lambda: None))
        self._btn_auto.setStyleSheet("font-weight: bold;")
        layout.addWidget(self._btn_auto)

        self._auto_label = QLabel("AUTO: OFF")
        self._auto_label.setAlignment(Qt.AlignCenter)
        self._auto_label.setStyleSheet("color: gray;")
        layout.addWidget(self._auto_label)

        layout.addWidget(self._hr())

        # 退出
        self._btn_quit = QPushButton("退出")
        self._btn_quit.clicked.connect(self.close)
        layout.addWidget(self._btn_quit)

    def closeEvent(self, event):
        if self._shutdown_cb:
            self._shutdown_cb()
        event.accept()

    def set_shutdown(self, cb):
        self._shutdown_cb = cb

    def _hr(self):
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        return f

    def set_auto_status(self, on):
        self._auto_label.setText(f"AUTO: {'ON' if on else 'OFF'}")
        self._auto_label.setStyleSheet(
            "color: #0f0; font-weight: bold;" if on else "color: gray;")
        self._btn_auto.setText(
            "关闭自动钓鱼 [F10]" if on else "开启自动钓鱼 [F10]")
