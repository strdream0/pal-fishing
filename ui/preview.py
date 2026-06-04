"""预览效果 — OpenCV 窗口, 可关闭不影响钓鱼"""
import cv2
import numpy as np

BAR_X1 = 34.2
BAR_Y1 = 27.4
BAR_X2 = 66.5
BAR_Y2 = 35.3


class PreviewWindow:
    def __init__(self):
        self._visible = False  # 默认关闭, F9开启

    def show(self, frame, green_rect, float_pos, bar_rect, result,
             control_enabled, controller):
        if not self._visible:
            return
        display = frame.copy()
        _draw_hud(display, green_rect, float_pos, result, bar_rect,
                  control_enabled, controller)
        fh, fw = display.shape[:2]
        scale = 960 / fw
        display = cv2.resize(display, (960, int(fh * scale)))
        cv2.imshow("预览效果", display)

    def check_close(self):
        if self._visible and cv2.getWindowProperty("预览效果", cv2.WND_PROP_VISIBLE) < 1:
            self._visible = False

    def toggle(self):
        if self._visible:
            try:
                cv2.destroyWindow("预览效果")
            except Exception:
                pass
            self._visible = False
        else:
            cv2.namedWindow("预览效果", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("预览效果", 960, 540)
            self._visible = True

    def close(self):
        try:
            cv2.destroyWindow("预览效果")
        except Exception:
            pass


def _draw_hud(img, green_rect, float_pos, result, bar_rect,
              control_enabled, controller):
    bx1, by1, bx2, by2 = bar_rect
    dh, dw = img.shape[:2]

    cv2.rectangle(img, (bx1, by1), (bx2, by2), (100, 100, 100), 1)

    if green_rect:
        gx, gy, gw, gh = green_rect
        cv2.rectangle(img, (gx, gy), (gx + gw, gy + gh), (0, 255, 0), 2)

    if float_pos:
        cv2.circle(img, float_pos, 8, (0, 0, 255), -1)

    color = {"IN": (0, 255, 0), "LEFT": (0, 165, 255),
             "RIGHT": (0, 165, 255)}.get(result, (100, 100, 100))
    cv2.putText(img, result if result != "?" else "...", (dw // 2 - 60, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, color, 3)

    cv2.rectangle(img, (0, dh - 28), (dw, dh), (0, 0, 0), -1)
    status = f"ESC:退出 | F8:截图 | F9:预览 | F10:控制 | F11:小窗 | F12:参数"
    if control_enabled:
        status += " [AUTO ON]"
        if controller:
            status += f" {controller.duty_str}"
    cv2.putText(img, status, (8, dh - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
