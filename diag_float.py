"""诊断浮标HSV：在滑轨范围内找所有橙色像素"""
import os
import cv2
import numpy as np

SCREENSHOT_DIR = "screenshots"
BAR_X1_PCT = 34.2
BAR_Y1_PCT = 27.4
BAR_X2_PCT = 66.5
BAR_Y2_PCT = 35.3

for f in sorted(os.listdir(SCREENSHOT_DIR)):
    if not f.endswith(".png") or f.startswith("screenshots"):
        continue
    bgr = cv2.imread(os.path.join(SCREENSHOT_DIR, f))
    h, w = bgr.shape[:2]
    bx1 = int(w * BAR_X1_PCT / 100)
    by1 = int(h * BAR_Y1_PCT / 100)
    bx2 = int(w * BAR_X2_PCT / 100)
    by2 = int(h * BAR_Y2_PCT / 100)

    bar = bgr[by1:by2, bx1:bx2, :]
    bar_hsv = cv2.cvtColor(bar, cv2.COLOR_BGR2HSV)
    bar_h, bar_s, bar_v = bar_hsv[:,:,0], bar_hsv[:,:,1], bar_hsv[:,:,2]

    print(f"\n{'='*50}")
    print(f"图片: {f}")
    print(f"滑轨内像素总数: {bar_h.size}")

    # 不同 S 阈值下的浮标候选像素数
    for s_min in [40, 50, 60, 70, 80, 90, 100, 110]:
        for v_min in [120, 140, 160, 180]:
            count = np.sum((bar_h >= 12) & (bar_h <= 48) & (bar_s >= s_min) & (bar_v >= v_min))
            if count > 20:
                pct = count / bar_h.size * 100
                marker = " ***" if count > 50 else ""
                print(f"  H[12,48] S>={s_min} V>={v_min}: {count}px ({pct:.2f}%){marker}")

    # 全范围扫描：看看 H 10-50 之间的像素到底长什么样
    orange_mask = (bar_h >= 10) & (bar_h <= 50)
    orange_pixels = bar_hsv[orange_mask]
    if len(orange_pixels) > 0:
        print(f"\n  橙色像素 (H 10-50) 共 {len(orange_pixels)} 个:")
        print(f"    H: mean={orange_pixels[:,0].mean():.1f}  min={orange_pixels[:,0].min()}  max={orange_pixels[:,0].max()}")
        print(f"    S: mean={orange_pixels[:,1].mean():.1f}  min={orange_pixels[:,1].min()}  max={orange_pixels[:,1].max()}")
        print(f"    V: mean={orange_pixels[:,2].mean():.1f}  min={orange_pixels[:,2].min()}  max={orange_pixels[:,2].max()}")
    else:
        print("\n  无橙色像素!")
