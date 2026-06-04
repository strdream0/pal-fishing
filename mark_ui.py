"""
手动标记钓鱼UI位置
用法: uv run python mark_ui.py

操作:
  鼠标 hover  → 看实时坐标和颜色
  左键点击    → 标记一个点（打印坐标）
  按 1 → 标记"绿色框左上角"
  按 2 → 标记"绿色框右下角"
  按 3 → 标记"浮标中心"
  按 S → 保存标记到文件
  按 Q → 退出
"""
import os
import cv2
import numpy as np

SCREENSHOT_DIR = "screenshots"

# 全局状态
marks = {}
current_label = None
img = None
window_name = "Mark UI - Hover to see coords | 1=绿框TL 2=绿框BR 3=浮标 S=Save Q=Quit"


def on_mouse(event, x, y, flags, param):
    global marks, current_label, img, mx, my
    if event == cv2.EVENT_MOUSEMOVE:
        mx, my = x, y
    if event == cv2.EVENT_LBUTTONDOWN:
        label = current_label or f"pt_{len(marks)}"
        marks[label] = (x, y)
        # 取该点颜色
        bgr = img[y, x]
        hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0][0]
        print(f"[MARK] {label}: ({x}, {y})  "
              f"BGR=({bgr[0]},{bgr[1]},{bgr[2]})  "
              f"HSV=({hsv[0]},{hsv[1]},{hsv[2]})  "
              f"相对=({x/img.shape[1]*100:.1f}%, {y/img.shape[0]*100:.1f}%)")


def draw_marks(display, mx=None, my=None):
    """在图上绘制已标记的点 + 当前鼠标位置"""
    h, w = display.shape[:2]

    # 当前鼠标坐标和颜色
    if mx is not None and my is not None and 0 <= mx < w and 0 <= my < h:
        bgr = display[my, mx]
        info = (f"({mx},{my}) rel=({mx/w*100:.1f}%,{my/h*100:.1f}%) "
                f"BGR=({bgr[0]},{bgr[1]},{bgr[2]})")
        # 底部信息条
        cv2.rectangle(display, (0, h - 22), (w, h), (40, 40, 40), -1)
        cv2.putText(display, info, (5, h - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)

    colors = {
        "green_tl": (0, 255, 0),
        "green_br": (0, 255, 0),
        "float_center": (0, 0, 255),
    }
    for label, (x, y) in marks.items():
        color = colors.get(label, (255, 255, 0))
        cv2.circle(display, (x, y), 5, color, -1)
        cv2.putText(display, label, (x + 8, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    if "green_tl" in marks and "green_br" in marks:
        x1, y1 = marks["green_tl"]
        x2, y2 = marks["green_br"]
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 1)


def main():
    global current_label, img, mx, my
    mx, my = -1, -1

    screenshots = [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(".png")]
    if not screenshots:
        print("未找到截图")
        return

    print("可用截图:")
    for i, f in enumerate(screenshots):
        print(f"  [{i}] {f}")
    choice = input("选择要标记的截图编号 (默认0): ").strip()
    idx = int(choice) if choice else 0
    filepath = os.path.join(SCREENSHOT_DIR, screenshots[idx])

    img = cv2.imread(filepath)
    print(f"\n载入: {screenshots[idx]}  ({img.shape[1]}x{img.shape[0]})")
    print("=" * 60)
    print("操作说明:")
    print("  鼠标悬停 → 看坐标和颜色")
    print("  按 1 → 标记绿色框左上角")
    print("  按 2 → 标记绿色框右下角")
    print("  按 3 → 标记浮标中心")
    print("  按 S → 打印并保存所有标记")
    print("  按 Q → 退出")
    print("=" * 60)

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_mouse)

    while True:
        display = img.copy()
        draw_marks(display, mx, my)

        # 控制显示比例
        h, w = display.shape[:2]
        scale = min(1400 / w, 900 / h, 1.0)
        if scale < 1.0:
            display = cv2.resize(display, (int(w * scale), int(h * scale)))

        cv2.imshow(window_name, display)

        key = cv2.waitKey(10) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('1'):
            current_label = "green_tl"
            print("[INFO] 下一个点击将标记: 绿色框左上角")
        elif key == ord('2'):
            current_label = "green_br"
            print("[INFO] 下一个点击将标记: 绿色框右下角")
        elif key == ord('3'):
            current_label = "float_center"
            print("[INFO] 下一个点击将标记: 浮标中心")
        elif key == ord('s'):
            print("\n===== 标记汇总 =====")
            for label, (x, y) in marks.items():
                rel_x = x / img.shape[1] * 100
                rel_y = y / img.shape[0] * 100
                bgr = img[y, x]
                hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0][0]
                print(f"  {label}: abs=({x},{y})  rel=({rel_x:.1f}%, {rel_y:.1f}%)")
                print(f"         BGR=({bgr[0]},{bgr[1]},{bgr[2]})  HSV=({hsv[0]},{hsv[1]},{hsv[2]})")
            if "green_tl" in marks and "green_br" in marks:
                x1, y1 = marks["green_tl"]
                x2, y2 = marks["green_br"]
                print(f"  绿框尺寸: w={x2-x1} h={y2-y1}")
                print(f"  绿框相对: x={x1/img.shape[1]*100:.1f}% y={y1/img.shape[0]*100:.1f}%")
                print(f"           w={(x2-x1)/img.shape[1]*100:.1f}% h={(y2-y1)/img.shape[0]*100:.1f}%")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
