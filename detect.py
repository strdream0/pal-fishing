"""
钓鱼UI识别 v8 — 水平H曲线找绿框边界，颜色找浮标
"""
import os
import cv2
import numpy as np

SCREENSHOT_DIR = "screenshots"
OUTPUT_DIR = "detect_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BAR_X1_PCT = 34.2
BAR_Y1_PCT = 27.4
BAR_X2_PCT = 66.5
BAR_Y2_PCT = 35.3


def detect(bgr, filename):
    h, w = bgr.shape[:2]

    bx1 = int(w * BAR_X1_PCT / 100)
    by1 = int(h * BAR_Y1_PCT / 100)
    bx2 = int(w * BAR_X2_PCT / 100)
    by2 = int(h * BAR_Y2_PCT / 100)

    bar = bgr[by1:by2, bx1:bx2, :]
    bar_hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)
    bar_h = bar_hsv[:, :, 0]
    bar_s = bar_hsv[:, :, 1]

    print(f"\n{'='*50}")
    print(f"图片: {filename}")

    # ── 绿框: 每列绿色像素占比 (采样: H58-87 S112-220 V220-255) ──
    bar_v = bar_hsv[:, :, 2]
    green_px = (bar_h > 58) & (bar_h < 87) & (bar_s > 110) & (bar_v > 220)
    col_ratio = np.mean(green_px, axis=0)
    is_green = col_ratio > 0.04

    edges = np.diff(np.concatenate([[0], is_green.astype(int), [0]]))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]

    green_rect = None
    segments = [(s, e) for s, e in zip(starts, ends) if e - s > 10]
    print(f"  绿列段: {[(s, e, e-s) for s, e in segments]}  (max_ratio={col_ratio.max():.2f})")

    if segments:
        # 合并间距 < 40px 的邻近段 (被浮标竖线切开)
        merged = [segments[0]]
        for s, e in segments[1:]:
            ps, pe = merged[-1]
            if s - pe < 40:
                merged[-1] = (ps, e)
            else:
                merged.append((s, e))
        s, e = max(merged, key=lambda x: x[1] - x[0])

        # 在绿框列范围内找垂直范围 (行级绿色占比)
        row_ratio = np.mean(green_px[:, s:e], axis=1)
        green_rows = np.where(row_ratio > 0.02)[0]
        if len(green_rows) > 0:
            gy1 = by1 + green_rows[0]
            gy2 = by1 + green_rows[-1] + 1
        else:
            gy1, gy2 = by1, by2

        green_rect = (bx1 + s, gy1, e - s, gy2 - gy1)
        print(f"[绿框] 宽={e-s}px 高={gy2-gy1}px  merge={[(a,b) for a,b in merged]}"
              f"  ({green_rect[0]},{green_rect[1]}) {e-s}x{gy2-gy1}")
    else:
        print(f"[绿框] 未找到 (max_ratio={col_ratio.max():.2f})")

    # ── 浮标: 简单颜色过滤 (v4方法) ──
    f_lower = np.array([10, 50, 180])
    f_upper = np.array([45, 255, 255])
    f_mask = cv2.inRange(bar_hsv, f_lower, f_upper)
    f_mask = cv2.morphologyEx(f_mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    f_contours, _ = cv2.findContours(f_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    float_pos = None
    if f_contours:
        best = max(f_contours, key=cv2.contourArea)
        if cv2.contourArea(best) > 15:
            fx, fy, fw, fh = cv2.boundingRect(best)
            float_pos = (bx1 + fx + fw // 2, by1 + fy + fh // 2)
            print(f"[浮标] area={cv2.contourArea(best):.0f} {fw}x{fh}")
            print(f"       ({float_pos[0]},{float_pos[1]})  "
                  f"rel=({float_pos[0]/w*100:.1f}%,{float_pos[1]/h*100:.1f}%)")
    if not float_pos:
        print("[浮标] 未找到")

    # ── 判定 ──
    if green_rect and float_pos:
        gx, gy, gw, gh = green_rect
        fx, fy = float_pos
        margin = 12  # 容差px，浮标竖线切绿框时边界有误差
        ok = (gx - margin) <= fx <= (gx + gw + margin)
        print(f"[判定] {'IN' if ok else 'OUT'}  (浮标x={fx} 绿框=[{gx},{gx+gw}] margin={margin})")

    # ── 调试 ──
    debug = bgr.copy()
    cv2.rectangle(debug, (bx1, by1), (bx2, by2), (255, 200, 0), 1)
    if green_rect:
        gx, gy, gw, gh = green_rect
        cv2.rectangle(debug, (gx, gy), (gx + gw, gy + gh), (0, 255, 0), 2)
    if float_pos:
        cv2.circle(debug, float_pos, 7, (0, 0, 255), -1)
        if green_rect:
            gcx = green_rect[0] + green_rect[2] // 2
            gcy = green_rect[1] + green_rect[3] // 2
            cv2.line(debug, float_pos, (gcx, gcy), (255, 255, 0), 1)

    cv2.imwrite(f"{OUTPUT_DIR}/{filename}_detect.png", debug)
    cv2.imwrite(f"{OUTPUT_DIR}/{filename}_float_mask.png", f_mask)
    cv2.imwrite(f"{OUTPUT_DIR}/{filename}_green_mask.png",
                (green_px.astype(np.uint8) * 255))


def main():
    for f in sorted(os.listdir(SCREENSHOT_DIR)):
        if f.endswith(".png") and not f.startswith("screenshots"):
            detect(cv2.imread(os.path.join(SCREENSHOT_DIR, f)), f)
    print(f"\n→ {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
