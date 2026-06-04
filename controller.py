"""Bang-Bang 控制器 — 前探 + 阈值触发"""
import time
import ctypes

INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", MOUSEINPUT)]


def _send_input(flags):
    inp = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dwFlags=flags))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _mouse_down():
    _send_input(MOUSEEVENTF_LEFTDOWN)


def _mouse_up():
    _send_input(MOUSEEVENTF_LEFTUP)


class BangBangController:
    """前探 bang-bang: 预测浮标位置 → 超出阈值就按/松"""

    def __init__(self, lookahead_ms=100, threshold=15):
        self.lookahead = lookahead_ms / 1000.0
        self.threshold = threshold
        self._prev_float_x = None
        self._prev_time = 0.0
        self._pressing = False

    def update(self, green_rect, float_pos, now):
        if green_rect is None or float_pos is None:
            if self._pressing:
                _mouse_up()
                self._pressing = False
            return

        gx, gy, gw, gh = green_rect
        green_cx = gx + gw // 2
        float_cx = float_pos[0]

        velocity = 0.0
        if self._prev_float_x is not None:
            dt = now - self._prev_time
            if 0 < dt < 2.0:
                velocity = (float_cx - self._prev_float_x) / dt

        predicted = float_cx + velocity * self.lookahead
        error = predicted - green_cx

        if error > self.threshold and not self._pressing:
            _mouse_down()
            self._pressing = True
        elif error < -self.threshold and self._pressing:
            _mouse_up()
            self._pressing = False

        self._prev_float_x = float_cx
        self._prev_time = now

    def stop(self):
        if self._pressing:
            _mouse_up()
            self._pressing = False

    @property
    def state(self):
        return 'press' if self._pressing else 'release'

    @property
    def _last_duty(self):
        return 1.0 if self._pressing else 0.0

    @property
    def duty_str(self):
        return f'BANG {"PRESS" if self._pressing else "RELEASE"}'

    @property
    def error_val(self):
        return 0.0

    _ff_active = False
