"""
诊断脚本：扫描滑轨区域，列出所有显著的颜色聚类
"""
import os
import cv2
import numpy as np

SCREENSHOT_DIR = "screenshots"
OUTPUT_DIR = "detect_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BAR_Y_TOP_PCT = 25
BAR_Y_BOT_PCT = 42


def analyze(filepath, label):
    bgr = cv2.imread(filepath)
    h, w = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    bar_y1 = int(h * BAR_Y_TOP_PCT / 100)
    bar_y2 = int(h * BAR_Y_BOT_PCT / 100)
    bar = bgr[bar_y1:bar_y2, :, :]
    bar_hsv = hsv[bar_y1:bar_y2, :, :]
    bar_h, bar_w = bar.shape[:2]

    print(f"\n{'='*60}")
    print(f"{label} — 滑轨区域 ({bar_w}x{bar_h})")
    print(f"{'='*60}")

    # ── 逐列分析，找每列的主色调 ──
    # 将像素按 HSV 聚类
    pixels = bar_hsv.reshape(-1, 3)

    # 每隔 N 列采样一列，看水平颜色分布
    sample_step = max(1, bar_w // 30)
    print(f"\n逐列采样 (每 {sample_step} 列):")
    print(f"{'X':>5s} {'%':>5s}  {'H均值':>6s} {'S均值':>6s} {'V均值':>6s}  {'B均值':>6s} {'G均值':>6s} {'R均值':>6s}")

    for col in range(0, bar_w, sample_step):
        col_pixels_bgr = bar[:, col, :]
        col_pixels_hsv = bar_hsv[:, col, :]
        b_avg = col_pixels_bgr[:, 0].mean()
        g_avg = col_pixels_bgr[:, 1].mean()
        r_avg = col_pixels_bgr[:, 2].mean()
        h_avg = col_pixels_hsv[:, 0].mean()
        s_avg = col_pixels_hsv[:, 1].mean()
        v_avg = col_pixels_hsv[:, 2].mean()
        pct = col / bar_w * 100
        print(f"{col:5d} {pct:4.1f}%  {h_avg:6.1f} {s_avg:6.1f} {v_avg:6.1f}  {b_avg:6.1f} {g_avg:6.1f} {r_avg:6.1f}")

    # ── 全局 HSV 统计 ──
    print(f"\n滑轨整体 HSV 分布:")
    print(f"  H: mean={bar_hsv[:,:,0].mean():.1f} std={bar_hsv[:,:,0].std():.1f}  "
          f"min={bar_hsv[:,:,0].min()} max={bar_hsv[:,:,0].max()}")
    print(f"  S: mean={bar_hsv[:,:,1].mean():.1f} std={bar_hsv[:,:,1].std():.1f}  "
          f"min={bar_hsv[:,:,1].min()} max={bar_hsv[:,:,1].max()}")
    print(f"  V: mean={bar_hsv[:,:,2].mean():.1f} std={bar_hsv[:,:,2].std():.1f}  "
          f"min={bar_hsv[:,:,2].min()} max={bar_hsv[:,:,2].max()}")

    # ── 在 bar 里找绿色像素 (H 50-90) ──
    for h_lo, h_hi in [(50, 90), (55, 85), (60, 80), (65, 75)]:
        for s_lo, s_hi in [(50, 255), (80, 255), (100, 255), (120, 255)]:
            mask = cv2.inRange(bar_hsv, np.array([h_lo, s_lo, 100]), np.array([h_hi, s_hi, 255]))
            count = cv2.countNonZero(mask)
            if count > 100:
                if count > 500:
                    print(f"  H[{h_lo},{h_hi}] S[{s_lo},{s_hi}] V[100,255] → {count} 像素 ***")

    # ── 保存滑轨截图 ──
    cv2.imwrite(f"{OUTPUT_DIR}/bar_{label}.png", bar)

    # ── 对整个 bar 做颜色量化找到主色调 ──
    # K-means 找 5 种主色
    Z = bar.reshape(-1, 3).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(Z, 5, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    centers = centers.astype(np.uint8)

    print(f"\n5 种主色调 (K-Means):")
    for i, c in enumerate(centers):
        chsv = cv2.cvtColor(np.uint8([[c]]), cv2.COLOR_BGR2HSV)[0][0]
        count = np.sum(labels == i)
        pct = count / len(labels) * 100
        print(f"  [{i}] BGR=({c[0]},{c[1]},{c[2]})  HSV=({chsv[0]},{chsv[1]},{chsv[2]})  "
              f"占比={pct:.1f}%")


def main():
    for fname in ["float_in.png", "float_out.png"]:
        path = os.path.join(SCREENSHOT_DIR, fname)
        if os.path.exists(path):
            analyze(path, fname)


if __name__ == "__main__":
    main()
