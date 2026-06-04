"""框选浮标区域，采样HSV颜色范围"""
import os
import cv2
import numpy as np

SCREENSHOT_DIR = "screenshots"

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
    screenshots = [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(".png")]
    if not screenshots:
        print("无截图")
        return
    print("可用截图:")
    for i, f in enumerate(screenshots):
        print(f"  [{i}] {f}")
    idx = int(input("选编号: ").strip() or "0")
    fpath = os.path.join(SCREENSHOT_DIR, screenshots[idx])

    img = cv2.imread(fpath)
    clone = img.copy()
    print(f"\n载入: {screenshots[idx]}  ({img.shape[1]}x{img.shape[0]})")
    print("拖拽框住浮标 → ENTER采样 → Q退出")

    cv2.namedWindow("Sample Float")
    cv2.setMouseCallback("Sample Float", on_mouse)

    while True:
        display = clone.copy()
        if start_pt[0] >= 0 and end_pt[0] >= 0:
            cv2.rectangle(display, start_pt, end_pt, (0, 0, 255), 1)

        cv2.imshow("Sample Float", display)
        key = cv2.waitKey(10) & 0xFF
        if key == ord('q'):
            break
        elif key == 13:  # Enter
            x1 = min(start_pt[0], end_pt[0])
            y1 = min(start_pt[1], end_pt[1])
            x2 = max(start_pt[0], end_pt[0])
            y2 = max(start_pt[1], end_pt[1])
            if x2 - x1 < 3 or y2 - y1 < 3:
                print("选区太小")
                continue

            roi = img[y1:y2, x1:x2, :]
            roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            h, s, v = roi_hsv[:,:,0].flatten(), roi_hsv[:,:,1].flatten(), roi_hsv[:,:,2].flatten()

            print(f"\n===== 浮标采样 =====")
            print(f"选区: ({x1},{y1})-({x2},{y2})  {x2-x1}x{y2-y1}  像素数: {len(h)}")
            print(f"H: mean={h.mean():.0f}  std={h.std():.0f}  5%={np.percentile(h,5):.0f}  95%={np.percentile(h,95):.0f}")
            print(f"S: mean={s.mean():.0f}  std={s.std():.0f}  5%={np.percentile(s,5):.0f}  95%={np.percentile(s,95):.0f}")
            print(f"V: mean={v.mean():.0f}  std={v.std():.0f}  5%={np.percentile(v,5):.0f}  95%={np.percentile(v,95):.0f}")
            h_lo = max(0, np.percentile(h,5)-5)
            h_hi = min(180, np.percentile(h,95)+5)
            s_lo = max(0, np.percentile(s,10)-10)
            v_lo = max(0, np.percentile(v,10)-15)
            print(f"建议: H=[{h_lo:.0f},{h_hi:.0f}]  S=[{s_lo:.0f},255]  V=[{v_lo:.0f},255]")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
