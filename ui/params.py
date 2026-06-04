"""参数面板 — 控制参数 + 颜色HSV + 自动采样"""
import os
import sys
import subprocess
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                                QLabel, QSlider, QGroupBox, QPushButton)
from PySide6.QtCore import Qt


class ParamsWindow:
    def __init__(self, controller=None):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self._controller = controller
        self._visible = False
        # 颜色HSV默认值(采样)
        self._green_h_lo, self._green_h_hi = 58, 87
        self._green_s_lo = 110
        self._green_v_lo = 220
        self._float_h_lo, self._float_h_hi = 20, 32
        self._float_s_lo = 105
        self._float_v_lo = 237
        self._on_color_change = None
        self._create()

    def _create(self):
        self.win = QWidget()
        self.win.setWindowTitle("参数调整")
        self.win.setFixedSize(340, 380)
        self.win.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)

        layout = QVBoxLayout(self.win)

        # 控制参数
        g1 = QGroupBox("控制参数")
        l1 = QVBoxLayout(g1)
        self._s_look = QSlider(Qt.Horizontal)
        self._s_look.setRange(0, 300)
        self._s_look.setValue(100)
        self._s_look.setTickInterval(50)
        self._s_look.setTickPosition(QSlider.TicksBelow)
        self._lb_look = QLabel("前探: 100ms — 追不上加大, 过头减小")
        l1.addWidget(self._lb_look)
        l1.addWidget(self._s_look)

        self._s_thr = QSlider(Qt.Horizontal)
        self._s_thr.setRange(0, 60)
        self._s_thr.setValue(15)
        self._s_thr.setTickInterval(10)
        self._s_thr.setTickPosition(QSlider.TicksBelow)
        self._lb_thr = QLabel("阈值: 15px — 敏感减小, 迟钝加大")
        l1.addWidget(self._lb_thr)
        l1.addWidget(self._s_thr)
        layout.addWidget(g1)

        # 绿框颜色
        g2 = QGroupBox("绿框颜色 HSV")
        l2 = QVBoxLayout(g2)
        self._gh_lo = self._make_hsv_sliders(l2, "H低", 0, 100, 58)
        self._gh_hi = self._make_hsv_sliders(l2, "H高", 0, 100, 87)
        self._gs_lo = self._make_hsv_sliders(l2, "S低", 0, 255, 110)
        self._gv_lo = self._make_hsv_sliders(l2, "V低", 0, 255, 220)
        layout.addWidget(g2)

        # 浮标颜色
        g3 = QGroupBox("浮标颜色 HSV")
        l3 = QVBoxLayout(g3)
        self._fh_lo = self._make_hsv_sliders(l3, "H低", 0, 100, 20)
        self._fh_hi = self._make_hsv_sliders(l3, "H高", 0, 100, 32)
        self._fs_lo = self._make_hsv_sliders(l3, "S低", 0, 255, 105)
        self._fv_lo = self._make_hsv_sliders(l3, "V低", 0, 255, 237)
        layout.addWidget(g3)

        # 自动采样
        btn = QPushButton("自动采样颜色 (先F8截图)")
        btn.clicked.connect(self._auto_sample)
        layout.addWidget(btn)

        # 连接控制参数变化
        self._s_look.valueChanged.connect(self._on_ctrl_change)
        self._s_thr.valueChanged.connect(self._on_ctrl_change)

    def _make_hsv_sliders(self, layout, name, lo, hi, val):
        row = QHBoxLayout()
        lbl = QLabel(name)
        lbl.setFixedWidth(25)
        row.addWidget(lbl)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(val)
        slider.valueChanged.connect(self._on_hsv_change)
        val_lbl = QLabel(str(val))
        val_lbl.setFixedWidth(30)
        row.addWidget(slider)
        row.addWidget(val_lbl)
        layout.addLayout(row)
        slider._val_lbl = val_lbl
        return slider

    def _on_ctrl_change(self):
        v_look = self._s_look.value()
        v_thr = self._s_thr.value()
        self._lb_look.setText(f"前探: {v_look}ms — 追不上加大, 过头减小")
        self._lb_thr.setText(f"阈值: {v_thr}px — 敏感减小, 迟钝加大")
        if self._controller:
            self._controller.lookahead = v_look / 1000.0
            self._controller.threshold = v_thr

    def _on_hsv_change(self):
        self._green_h_lo = self._gh_lo.value()
        self._green_h_hi = self._gh_hi.value()
        self._green_s_lo = self._gs_lo.value()
        self._green_v_lo = self._gv_lo.value()
        self._float_h_lo = self._fh_lo.value()
        self._float_h_hi = self._fh_hi.value()
        self._float_s_lo = self._fs_lo.value()
        self._float_v_lo = self._fv_lo.value()
        # 更新值标签
        for s in [self._gh_lo, self._gh_hi, self._gs_lo, self._gv_lo,
                   self._fh_lo, self._fh_hi, self._fs_lo, self._fv_lo]:
            s._val_lbl.setText(str(s.value()))
        if self._on_color_change:
            self._on_color_change(self.get_colors())

    def get_colors(self):
        return {
            "green_h_lo": self._green_h_lo, "green_h_hi": self._green_h_hi,
            "green_s_lo": self._green_s_lo, "green_v_lo": self._green_v_lo,
            "float_h_lo": self._float_h_lo, "float_h_hi": self._float_h_hi,
            "float_s_lo": self._float_s_lo, "float_v_lo": self._float_v_lo,
        }

    def set_on_color_change(self, callback):
        self._on_color_change = callback

    def _auto_sample(self):
        try:
            from ui.sampler import run_sampler
        except Exception:
            return
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        screenshot_dir = os.path.join(base, "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        try:
            files = sorted(
                [f for f in os.listdir(screenshot_dir) if f.endswith(".png")],
                key=lambda f: os.path.getmtime(os.path.join(screenshot_dir, f)),
                reverse=True,
            )
        except Exception:
            return
        img_path = os.path.join(screenshot_dir, files[0]) if files else None
        if not img_path:
            return

        def on_done(gh, fh):
            if gh is None:
                return
            self._gh_lo.setValue(gh["h_lo"])
            self._gh_hi.setValue(gh["h_hi"])
            self._gs_lo.setValue(gh["s_lo"])
            self._gv_lo.setValue(gh["v_lo"])
            self._fh_lo.setValue(fh["h_lo"])
            self._fh_hi.setValue(fh["h_hi"])
            self._fs_lo.setValue(fh["s_lo"])
            self._fv_lo.setValue(fh["v_lo"])
            self._on_hsv_change()

        self._sampler_widget = run_sampler(img_path, on_done)

    def set_controller(self, ctrl):
        self._controller = ctrl
        if ctrl:
            self._s_look.setValue(int(ctrl.lookahead * 1000))
            self._s_thr.setValue(int(ctrl.threshold))

    def toggle(self):
        self._visible = not self._visible
        if self._visible:
            self.win.show()
        else:
            self.win.hide()

    def close(self):
        self.win.hide()
        self.app.processEvents()
