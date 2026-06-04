"""
框选绿框区域，采样HSV颜色范围
用法: uv run python sample_green.py
操作: 鼠标拖拽画矩形框住绿框，按回车确认，按Q退出
"""
import os
import cv2
import numpy as np

SCREENSHOT_DIR = "screenshots"

# 全局
drawing = False
start_pt = (-1, -1)
end_pt = (-1, -1)
img = None


def on_mouse(event, x, y, flags, param):
    global drawing, start_pt, end_pt
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_pt = (x, y)
        end_pt = (x, y)
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        end_pt = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        end_pt = (x, y)


def main():
    global img

    screenshots = [f for f in os.listdir(SCREENSHOT_DIR)
                   if f.endswith(".png") and not f.startswith("screenshots")]
    if not screenshots:
        print("无截图")
        return

    print("可用截图:")
    for i, f in enumerate(screenshots):
        print(f"  [{i}] {f}")
    choice = input("选编号 (建议选 float_out, 绿框没被切开): ").strip()
    idx = int(choice) if choice else 0
    fpath = os.path.join(SCREENSHOT_DIR, screenshots[idx])

    img = cv2.imread(fpath)
    clone = img.copy()
    print(f"\n载入: {screenshots[idx]}  ({img.shape[1]}x{img.shape[0]})")
    print("用鼠标拖拽框住绿色框 → 按 ENTER 采样 → Q 退出")

    cv2.namedWindow("Sample Green")
    cv2.setMouseCallback("Sample Green", on_mouse)

    while True:
        display = clone.copy()
        if start_pt[0] >= 0 and end_pt[0] >= 0:
            cv2.rectangle(display, start_pt, end_pt, (0, 255, 0), 1)

            # 显示框选区域尺寸
            x1, y1 = min(start_pt[0], end_pt[0]), min(start_pt[1], end_pt[1])
            x2, y2 = max(start_pt[0], end_pt[0]), max(start_pt[1], end_pt[1])
            if x2 > x1 and y2 > y1:
                text = f"{x2-x1}x{y2-y1}  rel=({x1/img.shape[1]*100:.1f}%,{y1/img.shape[0]*100:.1f}%)"
                cv2.putText(display, text, (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

        cv2.imshow("Sample Green", display)
        key = cv2.waitKey(10) & 0xFF

        if key == ord('q'):
            break
        elif key == 13:  # Enter
            x1 = min(start_pt[0], end_pt[0])
            y1 = min(start_pt[1], end_pt[1])
            x2 = max(start_pt[0], end_pt[0])
            y2 = max(start_pt[1], end_pt[1])

            if x2 - x1 < 5 or y2 - y1 < 3:
                print("选区太小，重新框")
                continue

            roi = img[y1:y2, x1:x2, :]
            roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            h_vals = roi_hsv[:, :, 0].flatten()
            s_vals = roi_hsv[:, :, 1].flatten()
            v_vals = roi_hsv[:, :, 2].flatten()

            print(f"\n===== 绿框采样结果 =====")
            print(f"选区: ({x1},{y1})-({x2},{y2})  {x2-x1}x{y2-y1}")
            print(f"相对: ({x1/img.shape[1]*100:.1f}%,{y1/img.shape[0]*100:.1f}%)")
            print(f"像素数: {len(h_vals)}")
            print(f"\nH: mean={h_vals.mean():.1f}  std={h_vals.std():.1f}  "
                  f"min={h_vals.min()}  max={h_vals.max()}")
            print(f"   5%={np.percentile(h_vals,5):.0f}  25%={np.percentile(h_vals,25):.0f}  "
                  f"50%={np.percentile(h_vals,50):.0f}  75%={np.percentile(h_vals,75):.0f}  "
                  f"95%={np.percentile(h_vals,95):.0f}")
            print(f"\nS: mean={s_vals.mean():.1f}  std={s_vals.std():.1f}  "
                  f"min={s_vals.min()}  max={s_vals.max()}")
            print(f"   5%={np.percentile(s_vals,5):.0f}  25%={np.percentile(s_vals,25):.0f}  "
                  f"50%={np.percentile(s_vals,50):.0f}  75%={np.percentile(s_vals,75):.0f}  "
                  f"95%={np.percentile(s_vals,95):.0f}")
            print(f"\nV: mean={v_vals.mean():.1f}  std={v_vals.std():.1f}  "
                  f"min={v_vals.min()}  max={v_vals.max()}")
            print(f"   5%={np.percentile(v_vals,5):.0f}  25%={np.percentile(v_vals,25):.0f}  "
                  f"50%={np.percentile(v_vals,50):.0f}  75%={np.percentile(v_vals,75):.0f}  "
                  f"95%={np.percentile(v_vals,95):.0f}")

            # 建议阈值
            h_lo = max(0, np.percentile(h_vals, 5) - 10)
            h_hi = min(180, np.percentile(h_vals, 95) + 10)
            s_lo = max(0, np.percentile(s_vals, 5) - 10)
            v_lo = max(0, np.percentile(v_vals, 5) - 20)
            print(f"\n建议 inRange 范围: H=[{h_lo:.0f},{h_hi:.0f}]  "
                  f"S=[{s_lo:.0f},255]  V=[{v_lo:.0f},255]")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
