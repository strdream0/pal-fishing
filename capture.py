"""
幻兽帕鲁钓鱼 - 窗口内容捕获（非截屏）
即使窗口被遮挡也能读到游戏画面

用法: uv run python capture.py

原理: Windows Graphics Capture API → 直接读窗口渲染内容

全局热键（无需切换窗口，在游戏里直接按）:
  F8    快速截图，保存到 screenshots/
  F9    分析当前画面，检测钓鱼UI
  Esc   退出脚本
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

# ── Windows API：找窗口 ──────────────────────────────────────

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)


def get_window_rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def get_window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


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


def find_palworld_window():
    """按进程名 Palworld-Win64-Shipping.exe 自动定位"""
    results = []

    def enum_callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pname = get_window_process_name(hwnd)
        if "palworld" in pname.lower():
            x1, y1, x2, y2 = get_window_rect(hwnd)
            w, h = x2 - x1, y2 - y1
            if w > 200 and h > 200:
                title = get_window_title(hwnd)
                results.append({
                    "hwnd": hwnd, "title": title, "process": pname,
                    "left": x1, "top": y1, "width": w, "height": h,
                })
        return True

    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

    # 优先选游戏进程 (Palworld-Win64-Shipping.exe)，其次启动器 (Palworld.exe)
    if results:
        game_wins = [w for w in results if "shipping" in w["process"].lower()]
        if game_wins:
            results = game_wins  # 只用游戏进程的窗口
        # 如果多个窗口，选最大的
        results.sort(key=lambda w: w["width"] * w["height"], reverse=True)

    if not results:
        def enum_callback2(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            title = get_window_title(hwnd)
            if "pal" in title.lower():
                x1, y1, x2, y2 = get_window_rect(hwnd)
                w, h = x2 - x1, y2 - y1
                if w > 200 and h > 200:
                    pname = get_window_process_name(hwnd)
                    results.append({
                        "hwnd": hwnd, "title": title, "process": pname,
                        "left": x1, "top": y1, "width": w, "height": h,
                    })
            return True
        user32.EnumWindows(WNDENUMPROC(enum_callback2), 0)

    if not results:
        print("[!] 未找到帕鲁窗口，请确保游戏正在运行")
        print("    进程名应为: Palworld-Win64-Shipping.exe")
        return None

    win = results[0]
    print(f"[OK] 找到游戏窗口: \"{win['title']}\"")
    print(f"    进程: {win['process']}  大小: {win['width']}x{win['height']}")
    return win


# ── 帧缓冲 (线程安全) ────────────────────────────────────────

class FrameBuffer:
    """在捕获线程和主线程之间传递最新帧"""

    def __init__(self):
        self.lock = threading.Lock()
        self.frame = None
        self.ready = False
        self.fps = 0.0
        self.count = 0
        self._frame_count = 0
        self._fps_time = time.time()

    def put(self, frame_bgr):
        with self.lock:
            self.frame = frame_bgr
            if not self.ready:
                self.ready = True
                print("  [WGC] 首帧到达! ({})".format(frame_bgr.shape))
            self.count += 1
            self._frame_count += 1
            now = time.time()
            if now - self._fps_time >= 1.0:
                self.fps = self._frame_count / (now - self._fps_time)
                self._frame_count = 0
                self._fps_time = now

    def get(self):
        with self.lock:
            if not self.ready:
                return None, 0.0
            return self.frame.copy(), self.fps


# ── 钓鱼UI检测 ──────────────────────────────────────────────

def detect_fishing_ui(frame, debug_dir="debug"):
    """基于HSV颜色空间检测绿色目标区域和浮标"""
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    lower_green = np.array([40, 80, 80])
    upper_green = np.array([85, 255, 255])
    green_mask = cv2.inRange(hsv, lower_green, upper_green)

    kernel = np.ones((3, 3), np.uint8)
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
    green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    green_rect = None
    bar_region = None
    if contours:
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) > 100:
            gx, gy, gw, gh = cv2.boundingRect(largest)
            green_rect = (gx, gy, gw, gh)
            bar_margin = int(gw * 1.5)
            bar_region = (
                max(0, gx - bar_margin),
                max(0, gy - gh),
                min(w - max(0, gx - bar_margin), gw + bar_margin * 2),
                min(h - max(0, gy - gh), gh * 3),
            )

    float_pos = None
    if bar_region:
        bx, by, bw, bh = bar_region
        roi_hsv = hsv[by:by+bh, bx:bx+bw]
        white_mask = cv2.inRange(roi_hsv, np.array([0, 0, 180]), np.array([180, 40, 255]))
        w_contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if w_contours:
            lw = max(w_contours, key=cv2.contourArea)
            if cv2.contourArea(lw) > 20:
                wx, wy, ww, wh = cv2.boundingRect(lw)
                float_pos = (bx + wx + ww // 2, by + wy + wh // 2)

    os.makedirs(debug_dir, exist_ok=True)
    debug_img = frame.copy()
    if green_rect:
        gx, gy, gw, gh = green_rect
        cv2.rectangle(debug_img, (gx, gy), (gx + gw, gy + gh), (0, 255, 0), 2)
    if bar_region:
        bx, by, bw, bh = bar_region
        cv2.rectangle(debug_img, (bx, by), (bx + bw, by + bh), (255, 255, 0), 1)
    if float_pos:
        cv2.circle(debug_img, float_pos, 8, (0, 0, 255), -1)

    cv2.imwrite(f"{debug_dir}/detection_debug.png", debug_img)
    cv2.imwrite(f"{debug_dir}/green_mask.png", green_mask)

    return {
        "found": green_rect is not None,
        "green_rect": green_rect,
        "float_pos": float_pos,
        "bar_region": bar_region,
    }


# ── HUD ──────────────────────────────────────────────────────

def draw_hud(img, fps, win_title, detection=None, capture_mode="WGC"):
    dh, dw = img.shape[:2]
    overlay = img.copy()
    cv2.rectangle(overlay, (0, dh - 50), (dw, dh), (0, 0, 0), -1)
    img = cv2.addWeighted(img, 0.7, overlay, 0.3, 0)

    cv2.putText(img, f"Mode:{capture_mode} | FPS:{fps:.0f} | S:Save | A:Analyze | Q:Quit",
                (8, dh - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    cv2.putText(img, f"{win_title}  {dw}x{dh}",
                (8, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    if detection and detection.get("found"):
        gx, gy, gw, gh = detection["green_rect"]
        cv2.rectangle(img, (gx, gy), (gx + gw, gy + gh), (0, 255, 0), 1)
        if detection.get("float_pos"):
            cv2.circle(img, detection["float_pos"], 5, (0, 0, 255), -1)
        if detection.get("bar_region"):
            bx, by, bw, bh = detection["bar_region"]
            cv2.rectangle(img, (bx, by), (bx + bw, by + bh), (255, 255, 0), 1)
    elif detection:
        cv2.putText(img, "[X] Fishing UI not found", (8, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

    return img


# ── 主入口 ───────────────────────────────────────────────────

def main():
    os.makedirs("screenshots", exist_ok=True)

    print("=" * 50)
    print("  幻兽帕鲁 - 钓鱼画面捕获 v3")
    print("  使用 Windows Graphics Capture API")
    print("  窗口被遮挡也能读到游戏画面")
    print("=" * 50)

    # 1. 找游戏窗口
    print("\n[1/4] 查找游戏窗口...")
    win = find_palworld_window()
    if not win:
        print("[!] 请先启动游戏 (Palworld-Win64-Shipping.exe)")
        sys.exit(1)

    hwnd = win["hwnd"]
    win_w, win_h = win["width"], win["height"]

    # 2. 创建预览窗口（副屏或单屏角落）
    print("\n[2/4] 创建预览窗口...")
    import mss as mss_lib
    with mss_lib.mss() as tmp_sct:
        monitors = tmp_sct.monitors
    if len(monitors) >= 3:
        sec = monitors[2]
        pw = int(sec["width"] * 0.55)
        ph = int(sec["height"] * 0.55)
        px = sec["left"] + (sec["width"] - pw) // 2
        py = sec["top"] + (sec["height"] - ph) // 2
    else:
        pw, ph = 480, 270
        px, py = 10, 40

    cv2.namedWindow("Pal Capture (WGC)", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Pal Capture (WGC)", pw, ph)
    cv2.moveWindow("Pal Capture (WGC)", px, py)

    # 3. 启动窗口内容捕获（WGC）
    print("\n[3/4] 启动 Windows Graphics Capture...")
    fb = FrameBuffer()

    def on_frame_arrived(frame: wc.Frame, control: wc.InternalCaptureControl):
        """捕获回调 — 运行在捕获线程中"""
        try:
            bgra = frame.frame_buffer
            if bgra is not None:
                bgr = cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
                fb.put(bgr)
        except Exception:
            pass

    def on_closed():
        print("[!] 捕获会话关闭")

    capture = wc.WindowsCapture(
        cursor_capture=False,
        draw_border=False,
        window_hwnd=hwnd,
    )
    capture.event(on_frame_arrived)
    capture.event(on_closed)

    try:
        # start() 可能阻塞，放到独立线程
        cap_thread = threading.Thread(target=capture.start, daemon=True)
        cap_thread.start()
        time.sleep(0.5)  # 等捕获初始化
        if cap_thread.is_alive():
            print("[OK] WGC 捕获已启动 (window_hwnd={})".format(hwnd))
        else:
            raise RuntimeError("捕获线程立即退出")
        capture_mode = "WGC"
    except Exception as e:
        print(f"[FAIL] WGC 启动失败: {e}")
        print("[FALLBACK] 回退到 MSS 截屏模式")
        capture_mode = "MSS"
        import mss as mss2
        sct = mss2.mss()
        region = {
            "left": win["left"], "top": win["top"],
            "width": win_w, "height": win_h,
        }

    # 4. 主循环 — 使用 GetAsyncKeyState 轮询按键（无需管理员权限）
    #     F8=截图  F9=分析  Esc=退出
    VK_F8 = 0x77
    VK_F9 = 0x78
    VK_ESC = 0x1B

    def key_pressed(vk):
        """检查按键是否刚被按下（边缘检测，防止按住连发）"""
        return (user32.GetAsyncKeyState(vk) & 0x8000) != 0

    print("\n[4/4] 运行中...")
    print("  F8 → 截图  |  F9 → 分析  |  Esc → 退出")
    print("  全局生效，无需切换到预览窗口\n")

    screenshot_count = 0
    last_save = 0.0
    last_analyze = 0.0
    detection = None
    # 按键状态记忆，实现边缘检测
    prev_f8 = False
    prev_f9 = False
    prev_esc = False

    while True:
        now = time.time()

        # ── 轮询全局按键 ──
        cur_f8 = key_pressed(VK_F8)
        cur_f9 = key_pressed(VK_F9)
        cur_esc = key_pressed(VK_ESC)

        do_save = cur_f8 and not prev_f8
        do_analyze = cur_f9 and not prev_f9
        do_quit = cur_esc and not prev_esc

        prev_f8, prev_f9, prev_esc = cur_f8, cur_f9, cur_esc

        if do_quit:
            break

        # ── 拿帧 ──
        if capture_mode == "WGC":
            frame, fps = fb.get()
            if frame is None:
                time.sleep(0.005)
                continue
        else:
            import mss as mss2
            img = np.array(sct.grab(region))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            fps = 0

        # ── 执行 ──
        if do_save and now - last_save > 0.3:
            last_save = now
            screenshot_count += 1
            fname = f"screenshots/shot_{screenshot_count:03d}.png"
            cv2.imwrite(fname, frame)
            print(f"[SAVED] {fname}")

        if do_analyze and now - last_analyze > 0.3:
            last_analyze = now
            print("[ANALYZE] 检测钓鱼UI...")
            detection = detect_fishing_ui(frame)
            if detection["found"]:
                print(f"  Green: {detection['green_rect']}")
                print(f"  Float: {detection['float_pos']}")
            else:
                print("  -> 未检测到，查看 debug/detection_debug.png")

        # ── 预览 ──
        display = cv2.resize(frame, (pw, ph))
        display = draw_hud(display, fps, win["title"], detection, capture_mode)
        cv2.imshow("Pal Capture (WGC)", display)

        # OpenCV 窗口关闭时退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
        if cv2.getWindowProperty("Pal Capture (WGC)", cv2.WND_PROP_VISIBLE) < 1:
            break

    cv2.destroyAllWindows()
    print("Done.")


if __name__ == "__main__":
    main()
