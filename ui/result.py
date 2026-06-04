"""小窗查看 — 无边框半透明, 按比例显示绿框+浮标+状态"""
import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont


class ResultWidget(QWidget):
    def __init__(self, game_left=0, game_top=0):
        super().__init__()
        self._w, self._h = 300, 70
        self.setFixedSize(self._w, self._h)
        self.setWindowTitle("小窗查看")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.move(game_left + 10, game_top + 30)
        self._green = None
        self._float_x = None
        self._result = "?"
        self._auto_on = False
        self._detected = False
        self._visible = False

    def update_data(self, green_rect, float_pos, result, auto_on):
        self._green = green_rect
        self._float_x = float_pos[0] if float_pos else None
        self._result = result if result else "?"
        self._auto_on = auto_on
        self._detected = green_rect is not None and float_pos is not None
        if self._visible:
            self.repaint()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # 半透明背景
        p.fillRect(self.rect(), QColor(0, 0, 0, 160))
        # 边框
        p.setPen(QPen(QColor(80, 80, 80, 180), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRect(1, 1, self._w - 2, self._h - 2), 6, 6)

        bar_x, bar_w = 15, self._w - 30
        bar_y, bar_h = 22, 8

        # 滑轨底条
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(40, 40, 40))
        p.drawRoundedRect(QRect(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._green and self._float_x is not None:
            # 以浮标为中心, 显示范围 = 绿框宽度×4
            gx, gy, gw, gh = self._green
            view_w = gw * 4
            view_left = self._float_x - view_w / 2
            scale = bar_w / view_w

            # 绿框
            gx_s = bar_x + int((gx - view_left) * scale)
            gw_s = int(gw * scale)
            gx_s = max(bar_x, min(bar_x + bar_w - gw_s, gx_s))
            p.setBrush(QColor(0, 180, 0, 200))
            p.drawRoundedRect(QRect(gx_s, bar_y, max(2, gw_s), bar_h), 2, 2)

            # 浮标竖线
            fx_s = bar_x + int((self._float_x - view_left) * scale)
            fx_s = max(bar_x, min(bar_x + bar_w, fx_s))
            p.setPen(QPen(QColor(255, 60, 60, 220), 2))
            p.drawLine(fx_s, bar_y - 5, fx_s, bar_y + bar_h + 5)

        # 状态行
        font = QFont("Consolas", 10)
        p.setFont(font)

        # AUTO 状态 (左上角，始终显示)
        auto_color = QColor(0, 255, 0) if self._auto_on else QColor(120, 120, 120)
        p.setPen(auto_color)
        p.drawText(8, 14, f"AUTO:{'ON' if self._auto_on else 'OFF'}")

        # 检测状态 (右上角)
        if self._detected:
            p.setPen(QColor(0, 200, 0))
            p.drawText(self._w - 80, 14, "检测中")
        else:
            p.setPen(QColor(150, 150, 150))
            p.drawText(self._w - 80, 14, "等待检测...")

        # 判定结果 (底部)
        r = self._result if self._detected else "?"
        c = {"IN": QColor(0, 255, 0), "LEFT": QColor(0, 165, 255),
             "RIGHT": QColor(0, 165, 255)}.get(r, QColor(100, 100, 100))
        p.setPen(c)
        font2 = QFont("Consolas", 9)
        p.setFont(font2)
        p.drawText(bar_x, bar_y + bar_h + 16, f"判定: {r}")


class ResultWindow:
    def __init__(self, game_left=0, game_top=0):
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
        self.widget = ResultWidget(game_left, game_top)

    def show(self, green_rect, float_pos, result, auto_on):
        self.widget.update_data(green_rect, float_pos, result, auto_on)
        self.app.processEvents()

    def toggle(self):
        self.widget._visible = not self.widget._visible
        if self.widget._visible:
            self.widget.show()
        else:
            self.widget.hide()

    def close(self):
        self.widget.hide()
        self.app.processEvents()
