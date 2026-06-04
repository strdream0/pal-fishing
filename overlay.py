"""游戏叠层 — PySide6 透明窗口, 修复双屏DPI"""
import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QScreen


class OverlayWidget(QWidget):
    def __init__(self, left, top, w, h):
        super().__init__()
        self._x0, self._y0 = left, top
        self._w, self._h = w, h
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._green = None
        self._float = None
        self._bar = None
        self._result = "?"
        self._ctrl = ""
        self._show_hud = True
        self._auto_on = False
        self.setGeometry(left, top, w, h)
        self._x0, self._y0 = left, top
        self._w, self._h = w, h
        self.show()

    def update_data(self, green_rect, float_pos, bar_rect, result, ctrl_str=""):
        self._green = green_rect
        self._float = float_pos
        self._bar = bar_rect
        self._result = result
        self._ctrl = ctrl_str
        if not hasattr(self, '_dbg'):
            self._dbg = 0
        self._dbg += 1
        if self._dbg % 30 == 1:
            print(f"[overlay] frame#{self._dbg} bar={self._bar} green={self._green} float={self._float} result={self._result}")
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 0))
        if not hasattr(self, '_paint_cnt'):
            self._paint_cnt = 0
        self._paint_cnt += 1

        # 左下角常驻状态
        font = QFont("Consolas", 11, QFont.Bold)
        p.setFont(font)
        auto_color = QColor(0, 255, 0) if self._auto_on else QColor(120, 120, 120)
        hud_color = QColor(0, 255, 255) if self._show_hud else QColor(120, 120, 120)
        p.setPen(auto_color)
        p.drawText(10, self.height() - 20, f"AUTO: {'ON' if self._auto_on else 'OFF'}")
        p.setPen(hud_color)
        p.drawText(10, self.height() - 5, f"HUD: {'ON' if self._show_hud else 'OFF'}")

        if not self._show_hud:
            return

        # ── 完整 HUD ──
        if self._bar:
            bx1, by1, bx2, by2 = self._bar
            lx, ly = self.geometry().x(), self.geometry().y()
            p.setPen(QPen(QColor(100, 100, 100, 200), 1))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRect(bx1 - lx, by1 - ly, bx2 - bx1, by2 - by1))

        if self._green:
            gx, gy, gw, gh = self._green
            lx, ly = self.geometry().x(), self.geometry().y()
            p.setPen(QPen(QColor(0, 255, 0, 220), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRect(gx - lx, gy - ly, gw, gh))

        if self._float:
            fx, fy = self._float
            lx, ly = self.geometry().x(), self.geometry().y()
            p.setPen(QPen(QColor(255, 0, 0, 220), 1))
            p.setBrush(QBrush(QColor(255, 0, 0, 120)))
            p.drawEllipse(QPoint(fx - lx, fy - ly), 5, 5)

        # 判定大字
        font2 = QFont("Consolas", 28, QFont.Bold)
        p.setFont(font2)
        r = self._result
        c = {"IN": QColor(0, 255, 0), "LEFT": QColor(0, 165, 255),
             "RIGHT": QColor(0, 165, 255)}.get(r, QColor(100, 100, 100))
        p.setPen(c)
        p.drawText(self.width() // 2 - 50, 60, r if r != "?" else "...")

        # 控制状态
        if self._ctrl:
            p.setFont(QFont("Consolas", 10))
            p.setPen(QColor(255, 255, 0))
            p.drawText(10, 18, self._ctrl)


class GameOverlay:
    def __init__(self, left, top, w, h):
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)
        self.widget = OverlayWidget(left, top, w, h)
        self.widget.show()
        self.widget.raise_()
        self.app.processEvents()

    def draw_hud(self, green_rect, float_pos, bar_rect, result,
                 control_enabled=False, controller=None):
        ctrl = controller.duty_str if control_enabled and controller else ""
        self.widget._auto_on = control_enabled
        self.widget.update_data(green_rect, float_pos, bar_rect, result, ctrl)
        self.app.processEvents()

    def toggle_hud(self):
        self.widget._show_hud = not self.widget._show_hud

    def update_position(self, left, top, w, h):
        if (left, top, w, h) != (self.widget._x0, self.widget._y0, self.widget._w, self.widget._h):
            self.widget.setGeometry(left, top, w, h)
            self.widget._x0, self.widget._y0 = left, top
            self.widget._w, self.widget._h = w, h

    def update_position(self, left, top, w, h):
        self.widget._x0, self.widget._y0 = left, top
        self.widget.setGeometry(left, top, w, h)

    def close(self):
        self.widget.close()
        self.app.processEvents()
