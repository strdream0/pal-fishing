"""颜色采样向导 — 框选绿框+浮标, 自动填入HSV参数"""
import os
import sys
import cv2
import numpy as np
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QPushButton)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QImage, QPixmap


class SampleWidget(QWidget):
    def __init__(self, img_path, on_done):
        super().__init__()
        self._bgr = cv2.imread(img_path)
        if self._bgr is None:
            # print(f"[sampler] 找不到图片 {img_path}")
            on_done(None, None)
            return
        h, w = self._bgr.shape[:2]
        # 缩放适配屏幕
        scale = min(1200 / w, 800 / h, 1.0)
        self._sw, self._sh = int(w * scale), int(h * scale)
        self._scale = scale
        self._display = cv2.resize(self._bgr, (self._sw, self._sh))
        self.setFixedSize(self._sw, self._sh)
        self.setWindowTitle("颜色采样 — 步骤1: 框选绿框区域")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)

        self._step = 1
        self._green_rect = None
        self._float_rect = None
        self._drawing = False
        self._start = (0, 0)
        self._end = (0, 0)
        self._on_done = on_done
        self.show()

    def paintEvent(self, event):
        p = QPainter(self)
        # 显示图片
        rgb = cv2.cvtColor(self._display, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        p.drawPixmap(0, 0, QPixmap.fromImage(qimg))

        # 已确认的框
        if self._green_rect:
            x1, y1, x2, y2 = self._green_rect
            p.setPen(QPen(QColor(0, 255, 0, 200), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRect(x1, y1, x2 - x1, y2 - y1)

        if self._float_rect:
            x1, y1, x2, y2 = self._float_rect
            p.setPen(QPen(QColor(255, 0, 0, 200), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRect(x1, y1, x2 - x1, y2 - y1)

        # 正在拖的框
        if self._drawing:
            x1, y1 = self._start
            x2, y2 = self._end
            color = QColor(0, 255, 0) if self._step == 1 else QColor(255, 0, 0)
            p.setPen(QPen(color, 2))
            p.setBrush(Qt.NoBrush)
            p.drawRect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

        # 提示文字
        p.setPen(QColor(255, 255, 255))
        p.setBrush(QColor(0, 0, 0, 120))
        if self._step == 1:
            txt = "拖拽框选绿色区域 → 按 ENTER 确认"
        else:
            txt = "拖拽框选浮标区域 → 按 ENTER 确认 → 自动计算HSV"
        p.drawText(8, self._sh - 8, txt)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drawing = True
            self._start = (e.pos().x(), e.pos().y())
            self._end = self._start

    def mouseMoveEvent(self, e):
        if self._drawing:
            self._end = (e.pos().x(), e.pos().y())
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drawing = False
            self._end = (e.pos().x(), e.pos().y())
            self.update()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            x1, y1 = self._start
            x2, y2 = self._end
            if abs(x2 - x1) < 5 or abs(y2 - y1) < 3:
                return
            rx1 = int(min(x1, x2) / self._scale)
            ry1 = int(min(y1, y2) / self._scale)
            rx2 = int(max(x1, x2) / self._scale)
            ry2 = int(max(y1, y2) / self._scale)

            if self._step == 1:
                self._green_rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                self._green_raw = (rx1, ry1, rx2, ry2)
                self._step = 2
                self._drawing = False
                self.setWindowTitle("颜色采样 — 步骤2: 框选浮标区域")
                self.update()
            else:
                self._float_rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
                self._float_raw = (rx1, ry1, rx2, ry2)
                self._compute_and_close()
        elif e.key() == Qt.Key_Escape:
            self._on_done(None, None)
            self.close()

    def _compute_and_close(self):
        gh = self._hsv_range(self._green_raw)
        fh = self._hsv_range(self._float_raw)
        self._on_done(gh, fh)
        self.close()

    def _hsv_range(self, rect):
        rx1, ry1, rx2, ry2 = rect
        roi = self._bgr[ry1:ry2, rx1:rx2, :]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[:, :, 0].flatten(), hsv[:, :, 1].flatten(), hsv[:, :, 2].flatten()
        p5, p95 = int(np.percentile(h, 5)), int(np.percentile(h, 95))
        s5 = int(np.percentile(s, 5))
        v5 = int(np.percentile(v, 5))
        return {
            "h_lo": max(0, p5 - 5),
            "h_hi": min(180, p95 + 5),
            "s_lo": max(0, s5 - 10),
            "v_lo": max(0, v5 - 15),
        }


def run_sampler(img_path, on_done):
    """启动采样向导, 完成后回调 on_done(green_hsv, float_hsv)"""
    app = QApplication.instance() or QApplication(sys.argv)

    # 找最新截图
    if not img_path or not os.path.exists(img_path):
        screenshot_dir = "screenshots"
        files = [f for f in os.listdir(screenshot_dir) if f.endswith(".png")]
        if not files:
            # print("[sampler] 没有截图, 请先按F8截图")
            on_done(None, None)
            return
        files.sort(key=lambda f: os.path.getmtime(os.path.join(screenshot_dir, f)),
                   reverse=True)
        img_path = os.path.join(screenshot_dir, files[0])

    w = SampleWidget(img_path, on_done)
    return w
