"""
实时钓鱼识别 + 自动控制
用法: uv run python realtime.py
热键: Esc=退出  F8=截图  F10=切换自动控制
"""
import os
import sys
import time
import threading
import ctypes
from ctypes import wintypes

import cv2
import numpy as np
import windows_capture as wc
import mss

# ── Windows API 找窗口 ──────────────────────────────────────
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def get_window_rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def get_window_process_name(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
    if not handle:
        return ""
    name = ctypes.create_unicode_buffer(260)
    size = wintypes.DWORD(260)
    psapi.GetModuleBaseNameW(handle, None, name, size)
    kernel32.CloseHandle(handle)
    return name.value


def get_window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def find_palworld_window():
    results = []
    def enum_cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pname = get_window_process_name(hwnd)
        if "palworld" in pname.lower():
            x1, y1, x2, y2 = get_window_rect(hwnd)
            w, h = x2 - x1, y2 - y1
            if w > 200 and h > 200:
                results.append({"hwnd": hwnd, "title": get_window_title(hwnd),
                                "process": pname, "left": x1, "top": y1,
                                "width": w, "height": h})
        return True
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
    if results:
        game = [r for r in results if "shipping" in r["process"].lower()]
        if game:
            results = game
        results.sort(key=lambda r: r["width"] * r["height"], reverse=True)
    return results[0] if results else None


# ── 帧缓冲 ──────────────────────────────────────────────────
class FrameBuffer:
    def __init__(self):
        self.lock = threading.Lock()
        self.frame = None
        self.ready = False

    def put(self, frame):
        with self.lock:
            self.frame = frame
            self.ready = True

    def get(self):
        with self.lock:
            return self.frame.copy() if self.ready else None, None


# ── 识别参数 ─────────────────────────────────────────────────
BAR_X1 = 34.2
BAR_Y1 = 27.4
BAR_X2 = 66.5
BAR_Y2 = 35.3
FLOAT_MARGIN = 12


def detect(bgr):
    h, w = bgr.shape[:2]
    bx1 = int(w * BAR_X1 / 100)
    by1 = int(h * BAR_Y1 / 100)
    bx2 = int(w * BAR_X2 / 100)
    by2 = int(h * BAR_Y2 / 100)

    bar = bgr[by1:by2, bx1:bx2, :]
    bar_hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)
    bar_h, bar_s, bar_v = bar_hsv[:, :, 0], bar_hsv[:, :, 1], bar_hsv[:, :, 2]

    # ── 绿框: 每列绿色像素占比 ──
    green_px = (bar_h > 58) & (bar_h < 87) & (bar_s > 110) & (bar_v > 220)
    col_ratio = np.mean(green_px, axis=0)
    is_green = col_ratio > 0.04

    edges = np.diff(np.concatenate([[0], is_green.astype(int), [0]]))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]

    green_rect = None
    segments = [(s, e) for s, e in zip(starts, ends) if e - s > 10]
    if segments:
        merged = [segments[0]]
        for s, e in segments[1:]:
            ps, pe = merged[-1]
            if s - pe < 40:
                merged[-1] = (ps, e)
            else:
                merged.append((s, e))
        s, e = max(merged, key=lambda x: x[1] - x[0])
        # 垂直范围
        row_ratio = np.mean(green_px[:, s:e], axis=1)
        green_rows = np.where(row_ratio > 0.02)[0]
        gy1 = by1 + green_rows[0] if len(green_rows) > 0 else by1
        gy2 = by1 + green_rows[-1] + 1 if len(green_rows) > 0 else by2
        green_rect = (bx1 + s, gy1, e - s, gy2 - gy1)

    # ── 浮标 ──
    f_lower = np.array([20, 105, 237])
    f_upper = np.array([32, 255, 255])
    f_mask = cv2.inRange(bar_hsv, f_lower, f_upper)
    f_mask = cv2.morphologyEx(f_mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    f_contours, _ = cv2.findContours(f_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 跳变过滤: 取多个候选，选离上一帧位置最近的 (防止锁死假浮标)
    float_pos = None
    candidates = []
    for c in sorted(f_contours, key=cv2.contourArea, reverse=True)[:3]:
        if cv2.contourArea(c) > 15:
            fx, fy, fw, fh = cv2.boundingRect(c)
            candidates.append((bx1 + fx + fw // 2, by1 + fy + fh // 2))

    if candidates:
        global _last_float_x
        if '_last_float_x' not in dir():
            _last_float_x = None
        if _last_float_x is not None and len(candidates) > 1:
            # 选离上次位置 < 100px 的候选
            close = [p for p in candidates if abs(p[0] - _last_float_x) < 100]
            float_pos = close[0] if close else candidates[0]
        else:
            float_pos = candidates[0]
        _last_float_x = float_pos[0]

    # ── 判定 ──
    result = "?"
    if green_rect and float_pos:
        gx, gy, gw, gh = green_rect
        fx, fy = float_pos
        if fx < gx - FLOAT_MARGIN:
            result = "LEFT"
        elif fx > gx + gw + FLOAT_MARGIN:
            result = "RIGHT"
        else:
            result = "IN"

    return green_rect, float_pos, result, (bx1, by1, bx2, by2)


def draw_overlay(img, green_rect, float_pos, result, bar_rect,
                 control_enabled=False, mouse_state=None, duty=0.5,
                 pid_str="", error_val=0.0):
    """叠加 HUD"""
    bx1, by1, bx2, by2 = bar_rect
    dh, dw = img.shape[:2]

    # 滑轨框 (灰)
    cv2.rectangle(img, (bx1, by1), (bx2, by2), (100, 100, 100), 1)

    # 绿框 (绿)
    if green_rect:
        gx, gy, gw, gh = green_rect
        cv2.rectangle(img, (gx, gy), (gx + gw, gy + gh), (0, 255, 0), 2)

    # 浮标 (红点)
    if float_pos:
        cv2.circle(img, float_pos, 8, (0, 0, 255), -1)

    # 判定大字
    if result == "IN":
        color = (0, 255, 0)
        text = "IN"
    elif result == "LEFT":
        color = (0, 165, 255)
        text = "<< LEFT"
    elif result == "RIGHT":
        color = (0, 165, 255)
        text = "RIGHT >>"
    else:
        color = (100, 100, 100)
        text = "?"

    cv2.putText(img, text, (dw // 2 - 60, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, color, 3)

    # 底部信息
    cv2.rectangle(img, (0, dh - 28), (dw, dh), (0, 0, 0), -1)
    status = f"ESC:Quit | F8:Shot | F10:Control"
    if control_enabled:
        status += f" [AUTO {'ON' if control_enabled else 'OFF'}]"
        if mouse_state == 'press':
            status += " | MOUSE:DOWN"
        elif mouse_state == 'release':
            status += " | MOUSE:UP"
    if green_rect and float_pos:
        gx = green_rect[0]
        status += f" | Float@{float_pos[0]} Green@{gx}"
    cv2.putText(img, status, (8, dh - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

    # 控制状态 (右上角)
    if control_enabled:
        ctrl_color = (0, 255, 0) if mouse_state == 'press' else (0, 0, 255)
        ctrl_text = "PRESS" if mouse_state == 'press' else "RELEASE"
        cv2.putText(img, ctrl_text, (dw - 200, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, ctrl_color, 2)

        # duty 条形图
        bar_x, bar_y = dw - 200, 34
        bar_w, bar_h = 160, 6
        cv2.rectangle(img, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (80, 80, 80), 1)
        fill_w = int(bar_w * duty)
        bar_color = (0, 255, 0) if duty > 0.5 else (0, 0, 255)
        cv2.rectangle(img, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), bar_color, -1)

        # PID 各项
        lines = [
            f"duty={duty:.3f}",
            f"err={error_val:+.1f}px",
            pid_str,
        ]
        for i, line in enumerate(lines):
            cv2.putText(img, line, (bar_x, bar_y + 18 + i * 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.33, (200, 200, 200), 1)

    return img


# ── 鼠标控制 ─────────────────────────────────────────────────
# 使用 SendInput (无需管理员权限，游戏不拦截)

INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", MOUSEINPUT)]


def mouse_down():
    """按住左键"""
    inp = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTDOWN))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def mouse_up():
    """松开左键"""
    inp = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dwFlags=MOUSEEVENTF_LEFTUP))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


# ── 前探 Bang-Bang 控制器 ─────────────────────────────────────

class BangBangController:
    """预测误差 → 超出阈值直接按/松，无 PWM 无 PID"""

    def __init__(self, lookahead_ms=100, threshold=15, log_dir="logs"):
        self.lookahead = lookahead_ms / 1000.0
        self.threshold = threshold
        self._prev_float_x = None
        self._prev_time = 0.0
        self._pressing = False
        self._prev_green_x = None
        self._log_count = 0
        os.makedirs(log_dir, exist_ok=True)
        self._log_file = open(f"{log_dir}/bang_log.csv", "w")
        self._log_file.write("time,error,green_x,float_x,green_w,velocity,predicted,state,dgreen\n")
        self._last_duty = 0.0

    def update(self, green_rect, float_pos, now):
        if green_rect is None or float_pos is None:
            if self._pressing:
                mouse_up()
                self._pressing = False
            return

        gx, gy, gw, gh = green_rect
        green_cx = gx + gw // 2
        float_cx = float_pos[0]

        # 浮标速度
        velocity = 0.0
        if self._prev_float_x is not None:
            dt = now - self._prev_time
            if 0 < dt < 2.0:
                velocity = (float_cx - self._prev_float_x) / dt

        # 预测误差
        predicted = float_cx + velocity * self.lookahead
        error = predicted - green_cx

        # 控制
        if error > self.threshold and not self._pressing:
            mouse_down()
            self._pressing = True
        elif error < -self.threshold and self._pressing:
            mouse_up()
            self._pressing = False

        # 日志 (每 3 帧)
        self._last_duty = 1.0 if self._pressing else 0.0
        self._log_count += 1
        if self._log_count % 3 == 0:
            dg = green_cx - self._prev_green_x if self._prev_green_x is not None else 0
            self._log_file.write(
                f"{now:.3f},{error:.1f},{green_cx},{float_cx},{gw},"
                f"{velocity:.0f},{predicted:.0f},"
                f"{1 if self._pressing else 0},{dg:+d}\n"
            )
            self._log_file.flush()
            self._prev_green_x = green_cx

        self._prev_float_x = float_cx
        self._prev_time = now

    def stop(self):
        if self._pressing:
            mouse_up()
            self._pressing = False

    @property
    def state(self):
        return 'press' if self._pressing else 'release'

    @property
    def _last_duty(self):
        return 1.0 if self._pressing else 0.0

    @_last_duty.setter
    def _last_duty(self, v):
        pass  # read-only from _pressing

    @property
    def duty_str(self):
        return 'BANG ' + ('PRESS' if self._pressing else 'RELEASE')

    @property
    def error_val(self):
        return 0.0

    _ff_active = False

# ── (保留) PID 控制器 ─────────────────────────────────────────

class PIDController:
    """
    完整 PID + PWM 输出
    output = bias + Kp*error + Ki*integral + Kd*derivative
    duty = clamp(output, 0, 1)

    日志输出到 logs/ 目录，供 AI 调参
    """

    def __init__(self, cycle_ms=80, kp=0.01, ki=0.001, kd=0.005,
                 bias=0.35, deadzone=5, log_dir="logs",
                 ff_threshold=80, ff_duty=1.0,
                 bar_left=None, bar_right=None):
        self.cycle = cycle_ms / 1000.0
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.bias = bias
        self.deadzone = deadzone
        self.ff_threshold = ff_threshold  # 浮标速度阈值 (px/s)
        self.ff_duty = ff_duty            # 触发前馈时的占空比
        self.bar_left = bar_left          # 滑轨左边界 (绝对坐标)
        self.bar_right = bar_right        # 滑轨右边界
        self._base_bias = bias            # 基础 bias, 边界动态调整

        self._cycle_start = 0.0
        self._pressing = False
        self._active = False
        self._last_duty = 0.5

        # PID 状态
        self._prev_error = 0.0
        self._integral = 0.0
        self._last_time = 0.0
        self._prev_float_x = None
        self._ff_active = False

        # 数据日志
        self._p_term = 0.0
        self._i_term = 0.0
        self._d_term = 0.0
        self._error = 0.0

        os.makedirs(log_dir, exist_ok=True)
        self._log_file = open(f"{log_dir}/pid_log.csv", "w")
        self._log_file.write("time,error,green_x,float_x,green_w,P,I,D,output,duty,state,ff,press_ms,dgreen\n")
        self._last_green_x = None
        self._press_start = None
        self._log_count = 0

    def update(self, green_rect, float_pos, now):
        if green_rect is None or float_pos is None:
            if self._pressing:
                mouse_up()
                self._pressing = False
                self._active = False
            return

        gx, gy, gw, gh = green_rect
        green_cx = gx + gw // 2
        float_cx = float_pos[0]

        error = float_cx - green_cx

        # dt 计算 (前馈和 PID 共用)
        dt = now - self._last_time if self._last_time > 0 else self.cycle
        if dt <= 0:
            dt = self.cycle

        # ── 前馈：检测浮标速度，突然跳变直接满输出 ──
        if dt > 2.0:
            self._prev_float_x = None
            self._integral = 0
        # 只在误差较大且浮标远离中心时触发
        dz = max(self.deadzone, gw * 0.10)
        if self._prev_float_x is not None and dt > 0 and dt < 2.0 and abs(error) > dz * 3:
            float_velocity = (float_cx - self._prev_float_x) / dt
            if error > 0 and float_velocity > self.ff_threshold:
                self._last_duty = self.ff_duty
                self._integral = 0
                self._prev_float_x = float_cx
                self._prev_error = error
                self._last_time = now
                self._ff_active = True
                self._log(now, error, green_cx, float_cx, gw, int(self._last_duty * self.cycle * 1000))
                self._run_pwm(now, self.ff_duty)
                return
            elif error < 0 and float_velocity < -self.ff_threshold:
                self._last_duty = 1.0 - self.ff_duty
                self._integral = 0
                self._prev_float_x = float_cx
                self._prev_error = error
                self._last_time = now
                self._ff_active = True
                self._log(now, error, green_cx, float_cx, gw, int(self._last_duty * self.cycle * 1000))
                self._run_pwm(now, 1.0 - self.ff_duty)
                return
            # 误差小或向中心移动 → PID 处理
        self._prev_float_x = float_cx
        self._ff_active = False

        # 死区
        dz = max(self.deadzone, gw * 0.10)
        if abs(error) < dz:
            error = 0

        # ── PID 计算 ──
        self._last_time = now

        # P
        self._p_term = self.kp * error

        # I (抗积分饱和 + 限幅 + 方向反转清零)
        # 误差过零时重置积分
        if self._prev_error != 0 and error * self._prev_error < 0:
            self._integral = 0
        self._integral += error * dt
        # 输出饱和时停止积分
        if (self._last_duty >= 1.0 and error > 0) or \
           (self._last_duty <= 0.0 and error < 0):
            self._integral -= error * dt
        # 限幅 ±0.03
        self._integral = np.clip(self._integral, -30, 30)
        self._i_term = self.ki * self._integral

        # D (误差变化率)
        derivative = (error - self._prev_error) / dt if dt > 0 else 0
        self._d_term = self.kd * derivative
        self._prev_error = error

        # ── 动态 bias: 仅左侧边界保护 (绿框宽度×0.7) ──
        if self.bar_left is not None:
            left_margin = gw * 0.7  # 保护范围 = 绿框宽的 70%
            left_dist = green_cx - self.bar_left
            if left_dist < left_margin:
                # 越靠左 bias 越低，从 0.72 降到 0.50
                self.bias = self._base_bias - (1.0 - left_dist / left_margin) * 0.22
            else:
                self.bias = self._base_bias

        # 总输出
        output = self.bias + self._p_term + self._i_term + self._d_term
        duty = np.clip(output, 0.0, 1.0)
        self._last_duty = duty
        self._error = error
        self._log(now, error, green_cx, float_cx, gw, int(self._last_duty * self.cycle * 1000))
        self._run_pwm(now, duty)

    def _run_pwm(self, now, duty):
        """PWM 输出到鼠标，追踪每周期按压时长"""
        elapsed = now - self._cycle_start
        if elapsed >= self.cycle or not self._active:
            self._cycle_start = now
            self._active = True
            self._press_ms_sum = (self._last_duty * self.cycle * 1000) if hasattr(self, '_press_ms_sum') else 0
            elapsed = 0

        should_press = elapsed < (duty * self.cycle)

        if should_press and not self._pressing:
            mouse_down()
            self._pressing = True
        elif not should_press and self._pressing:
            mouse_up()
            self._pressing = False

    def _log(self, now, error, green_cx, float_cx, gw, press_ms=0):
        self._log_count += 1
        if self._log_count % 3 == 0:
            dgreen = green_cx - self._last_green_x if self._last_green_x is not None else 0
            self._log_file.write(
                f"{now:.3f},{error:.1f},{green_cx},{float_cx},{gw},"
                f"{self._p_term:.4f},{self._i_term:.4f},{self._d_term:.4f},"
                f"{self.bias+self._p_term+self._i_term+self._d_term:.4f},"
                f"{self._last_duty:.3f},"
                f"{1 if self._pressing else 0},"
                f"{1 if self._ff_active else 0},"
                f"{press_ms:.0f},{dgreen:+d}\n"
            )
            self._log_file.flush()
            self._last_green_x = green_cx

    def stop(self):
        if self._pressing:
            mouse_up()
            self._pressing = False
            self._active = False
        if self._log_file:
            self._log_file.close()

    @property
    def state(self):
        return 'press' if self._pressing else 'release'

    @property
    def duty_str(self):
        return f"P={self._p_term:+.3f} I={self._i_term:+.3f} D={self._d_term:+.3f}"

    @property
    def error_val(self):
        return self._error


# ── 主入口 ───────────────────────────────────────────────────
def main():
    os.makedirs("screenshots", exist_ok=True)

    print("=" * 50)
    print("  实时钓鱼识别")
    print("=" * 50)

    print("\n[1/3] 查找游戏窗口...")
    win = find_palworld_window()
    if not win:
        print("[!] 请启动游戏")
        sys.exit(1)
    print(f"[OK] {win['title']}  {win['width']}x{win['height']}")

    print("\n[2/3] 启动捕获...")
    fb = FrameBuffer()

    def on_frame_arrived(frame, control):
        try:
            bgra = frame.frame_buffer
            if bgra is not None:
                fb.put(cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR))
        except Exception:
            pass

    def on_closed():
        print("[!] 捕获关闭")

    capture = wc.WindowsCapture(cursor_capture=False, draw_border=False,
                                window_hwnd=win["hwnd"])
    capture.event(on_frame_arrived)
    capture.event(on_closed)

    try:
        t = threading.Thread(target=capture.start, daemon=True)
        t.start()
        time.sleep(0.5)
        if not t.is_alive():
            raise RuntimeError("启动失败")
        print("[OK] WGC 运行中")
        mode = "WGC"
    except Exception as e:
        print(f"[WARN] WGC失败({e}), 回退MSS")
        mode = "MSS"
        sct = mss.mss()
        region = {"left": win["left"], "top": win["top"],
                  "width": win["width"], "height": win["height"]}

    print("\n[3/3] 运行中  Esc=退出  F8=截图  F10=自动控制\n")

    main._test_before = None  # 物理测试用
    VK_ESC, VK_F8, VK_F10 = 0x1B, 0x77, 0x79
    prev_esc = prev_f8 = prev_f10 = False
    shot_count = 0
    last_shot = 0.0
    control_enabled = False
    bar_left = int(win["width"] * 34.2 / 100)
    bar_right = int(win["width"] * 66.5 / 100)
    controller = BangBangController(lookahead_ms=150, threshold=15)

    while True:
        now = time.time()

        # ── 按键 ──
        cur_esc = (user32.GetAsyncKeyState(VK_ESC) & 0x8000) != 0
        cur_f8 = (user32.GetAsyncKeyState(VK_F8) & 0x8000) != 0
        cur_f10 = (user32.GetAsyncKeyState(VK_F10) & 0x8000) != 0

        if cur_esc and not prev_esc:
            break
        if cur_f8 and not prev_f8 and now - last_shot > 0.3:
            last_shot = now
            shot_count += 1
            cv2.imwrite(f"screenshots/shot_{shot_count:03d}.png", frame)
            print(f"[SAVED] screenshots/shot_{shot_count:03d}.png")
        if cur_f10 and not prev_f10:
            control_enabled = not control_enabled
            print(f"[AUTO] {'ON' if control_enabled else 'OFF'}")
            if not control_enabled:
                controller.stop()

        prev_esc, prev_f8, prev_f10 = cur_esc, cur_f8, cur_f10

        # 获取帧
        if mode == "WGC":
            frame, _ = fb.get()
            if frame is None:
                time.sleep(0.005)
                continue
        else:
            img = np.array(sct.grab(region))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        # 识别
        green_rect, float_pos, result, bar_rect = detect(frame)

        # ── 物理测试热键 (F2=20ms F3=50ms F4=100ms) ──
        _test_before = getattr(main, '_test_before', None)
        if _test_before is not None and green_rect:
            dx = green_rect[0] - _test_before
            print(f"[TEST] 绿框位移 = {dx:+d}px (从 {_test_before} 到 {green_rect[0]})")
            main._test_before = None
            controller.stop()

        for vk, action, label in [(0x71, 'press', 'F2:按住300ms'),
                                   (0x72, 'release', 'F3:松手300ms'),
                                   (0x73, 'pulse', 'F4:按100ms+松200ms')]:
            cur = (user32.GetAsyncKeyState(vk) & 0x8000) != 0
            prev_key = f'_prev_{vk}'
            if cur and not getattr(main, prev_key, False) and green_rect:
                main._test_before = green_rect[0]
                if action == 'press':
                    mouse_down()
                    time.sleep(0.3)
                    mouse_up()
                elif action == 'release':
                    mouse_up()
                    time.sleep(0.3)
                elif action == 'pulse':
                    mouse_down()
                    time.sleep(0.1)
                    mouse_up()
                    time.sleep(0.2)
                print(f"[TEST] {label}, 等待结果...")
            setattr(main, prev_key, cur)

        # 控制
        if main._test_before is None and control_enabled:
            controller.update(green_rect, float_pos, now)

        # 在原图上画 overlay，再等比缩放显示
        display = frame.copy()
        display = frame.copy()
        display = draw_overlay(display, green_rect, float_pos, result, bar_rect,
                               control_enabled,
                               controller.state if control_enabled else None,
                               controller._last_duty if control_enabled else 0.5,
                               controller.duty_str if control_enabled else "",
                               controller.error_val if control_enabled else 0.0)
        fh, fw = display.shape[:2]
        scale = 960 / fw
        display = cv2.resize(display, (960, int(fh * scale)))
        cv2.imshow("Fishing", display)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    controller.stop()
    cv2.destroyAllWindows()
    print("Done.")


if __name__ == "__main__":
    main()
