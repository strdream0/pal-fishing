"""
深入分析：聚焦绿色框区域，对比 float_in vs float_out
找出浮标的精确颜色特征
"""
import os
import cv2
import numpy as np

SCREENSHOT_DIR = "screenshots"
OUTPUT_DIR = "analysis_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 已知的绿色框位置（来自上一次分析，相对百分比）
GREEN_X_PCT = 3.6   # %
GREEN_Y_PCT = 91.0  # %
GREEN_W_PCT = 11.7  # %
GREEN_H_PCT = 1.7   # %

# 滑轨整条
BAR_Y_PCT = 90.2     # %
BAR_H_PCT = 5.2      # % (39/748)


def load_and_crop(path):
    bgr = cv2.imread(path)
    h, w = bgr.shape[:2]

    # 绿色框绝对坐标
    gx = int(w * GREEN_X_PCT / 100)
    gy = int(h * GREEN_Y_PCT / 100)
    gw = int(w * GREEN_W_PCT / 100)
    gh = int(h * GREEN_H_PCT / 100)

    # 滑轨整条（从绿框左右各扩展一些，覆盖整条 bar）
    bar_x = 0
    bar_w = int(w * 0.6)  # 假设 bar 占画面 60% 宽
    bar_y = int(h * BAR_Y_PCT / 100)
    bar_h = int(h * BAR_H_PCT / 100)

    green_roi = bgr[gy:gy+gh, gx:gx+gw]       # 绿框
    bar_roi = bgr[bar_y:bar_y+bar_h, bar_x:bar_x+bar_w]  # 整条滑轨

    return {
        "bgr": bgr,
        "size": (w, h),
        "green_rect": (gx, gy, gw, gh),
        "green_roi": green_roi,
        "bar_rect": (bar_x, bar_y, bar_w, bar_h),
        "bar_roi": bar_roi,
    }


def analyze_pixels(roi, name):
    """详细分析一个 ROI 的像素分布"""
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    print(f"\n  [{name}] 尺寸={roi.shape[1]}x{roi.shape[0]}")
    print(f"    BGR 均值: B={roi[:,:,0].mean():.1f} G={roi[:,:,1].mean():.1f} R={roi[:,:,2].mean():.1f}")
    print(f"    HSV 均值: H={hsv[:,:,0].mean():.1f} S={hsv[:,:,1].mean():.1f} V={hsv[:,:,2].mean():.1f}")
    print(f"    Gray均值: {gray.mean():.1f}")
    print(f"    BGR 标准差: B={roi[:,:,0].std():.1f} G={roi[:,:,1].std():.1f} R={roi[:,:,2].std():.1f}")
    print(f"    Gray标准差: {gray.std():.1f}")
    print(f"    最小-最大 Gray: {gray.min()}-{gray.max()}")
    print(f"    最小-最大 V:   {hsv[:,:,2].min()}-{hsv[:,:,2].max()}")

    # 逐列分析亮度（找出亮斑在哪一列）
    col_brightness = gray.mean(axis=0)
    brightest_col = int(np.argmax(col_brightness))
    print(f"    最亮列: {brightest_col} (亮度={col_brightness[brightest_col]:.1f})")

    return {
        "hsv_mean": (hsv[:,:,0].mean(), hsv[:,:,1].mean(), hsv[:,:,2].mean()),
        "bgr_mean": (roi[:,:,0].mean(), roi[:,:,1].mean(), roi[:,:,2].mean()),
        "gray_mean": gray.mean(),
        "gray_std": gray.std(),
        "col_brightness": col_brightness,
        "brightest_col": brightest_col,
    }


def diff_rois(roi_a, roi_b, name_a, name_b):
    """对比两个 ROI 的差异"""
    diff = cv2.absdiff(roi_a, roi_b)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    print(f"\n  [{name_a} vs {name_b}]")
    print(f"    差异像素数: {np.count_nonzero(gray_diff > 30)} / {gray_diff.size}")
    print(f"    最大差异: {gray_diff.max()}")
    print(f"    平均差异: {gray_diff.mean():.1f}")

    # 找出差异最大的坐标
    max_pos = np.unravel_index(np.argmax(gray_diff), gray_diff.shape)
    print(f"    最大差异位置: y={max_pos[0]}, x={max_pos[1]}")

    cv2.imwrite(f"{OUTPUT_DIR}/diff.png", cv2.applyColorMap(gray_diff, cv2.COLORMAP_JET))

    return gray_diff


def main():
    f_in = os.path.join(SCREENSHOT_DIR, "float_in.png")
    f_out = os.path.join(SCREENSHOT_DIR, "float_out.png")

    print("=" * 60)
    print("深度分析: 绿色框 + 浮标")
    print("=" * 60)

    data_in = load_and_crop(f_in)
    data_out = load_and_crop(f_out)

    w, h = data_in["size"]
    gx, gy, gw, gh = data_in["green_rect"]
    print(f"\n图像尺寸: {w}x{h}")
    print(f"绿色框(绝对): x={gx} y={gy} w={gw} h={gh}")
    print(f"绿色框(相对): x={GREEN_X_PCT}% y={GREEN_Y_PCT}% w={GREEN_W_PCT}% h={GREEN_H_PCT}%")

    # ── 1. 绿色框内像素分析 ──
    print(f"\n{'='*40}")
    print("1. 绿色框内部像素对比")
    print(f"{'='*40}")
    analyze_pixels(data_in["green_roi"], "float_in 绿框内")
    analyze_pixels(data_out["green_roi"], "float_out 绿框内")
    diff_rois(data_in["green_roi"], data_out["green_roi"], "in", "out")

    # ── 2. 滑轨整体分析 ──
    print(f"\n{'='*40}")
    print("2. 整条滑轨水平亮度分布")
    print(f"{'='*40}")

    for label, data in [("float_in", data_in), ("float_out", data_out)]:
        bar = data["bar_roi"]
        gray_bar = cv2.cvtColor(bar, cv2.COLOR_BGR2GRAY)
        col_bright = gray_bar.mean(axis=0)

        # 找亮度峰值（可能的浮标位置）
        # 浮标应该是一个局部的亮度峰
        from scipy import ndimage
        try:
            # 用滑窗找亮度异常区域（比周围亮很多的地方）
            window = max(5, bar.shape[1] // 20)
            local_avg = ndimage.uniform_filter1d(col_bright, window)
            deviation = col_bright - local_avg
            peak_col = int(np.argmax(deviation))
            print(f"\n  [{label}]")
            print(f"    滑轨宽度: {bar.shape[1]}px")
            print(f"    整体平均亮度: {gray_bar.mean():.1f}")
            print(f"    亮度最高列: {int(np.argmax(col_bright))} (值={col_bright.max():.1f})")
            print(f"    局部偏差最大列: {peak_col} (偏差={deviation[peak_col]:.1f})")
            print(f"    该列全局坐标 x ≈ {peak_col}, 相对={peak_col/w*100:.1f}%")
            print(f"    绿框范围: x={gx}-{gx+gw} (相对={gx/w*100:.1f}%-{(gx+gw)/w*100:.1f}%)")
            in_green = gx <= peak_col <= gx + gw
            print(f"    浮标是否在绿框内: {'YES' if in_green else 'NO'}")
        except ImportError:
            # scipy 不可用，用简单方法
            peak_col = int(np.argmax(col_bright))
            print(f"\n  [{label}]")
            print(f"    亮度最高列: {peak_col} (值={col_bright.max():.1f})")
            print(f"    绿框范围: x={gx}-{gx+gw}")

        # 保存滑轨亮度曲线图
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(12, 3))
        ax.plot(col_bright, 'b-', linewidth=1, label='列平均亮度')
        ax.axvline(x=gx, color='g', linestyle='--', label='绿框左边界')
        ax.axvline(x=gx+gw, color='g', linestyle='--', label='绿框右边界')
        ax.axvline(x=peak_col, color='r', linestyle='-', linewidth=2, label=f'亮度峰 ({peak_col})')
        ax.set_title(f'{label} - 滑轨水平亮度分布')
        ax.set_xlabel('X 像素位置')
        ax.set_ylabel('平均亮度')
        ax.legend()
        fig.tight_layout()
        fig.savefig(f"{OUTPUT_DIR}/bar_profile_{label}.png", dpi=100)
        plt.close(fig)

    # ── 3. 浮标的颜色特征 ──
    print(f"\n{'='*40}")
    print("3. 浮标颜色采样")
    print(f"{'='*40}")

    # 在 float_in 图中，浮标应该在绿框范围内
    # 取绿框内亮度最高的 N 个像素，看它们的 HSV 分布
    for label, data in [("float_in", data_in), ("float_out", data_out)]:
        roi = data["green_roi"]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # 取亮度前 20% 的像素
        threshold = np.percentile(gray, 80)
        bright_mask = gray >= threshold
        bright_hsv = hsv[bright_mask]

        if len(bright_hsv) > 0:
            print(f"\n  [{label}] 绿框内亮度前20%像素 (共{len(bright_hsv)}个):")
            print(f"    HSV: H={bright_hsv[:,0].mean():.1f}±{bright_hsv[:,0].std():.1f}")
            print(f"         S={bright_hsv[:,1].mean():.1f}±{bright_hsv[:,1].std():.1f}")
            print(f"         V={bright_hsv[:,2].mean():.1f}±{bright_hsv[:,2].std():.1f}")
            print(f"    H范围: {bright_hsv[:,0].min():.0f}-{bright_hsv[:,0].max():.0f}")
            print(f"    S范围: {bright_hsv[:,1].min():.0f}-{bright_hsv[:,1].max():.0f}")
            print(f"    V范围: {bright_hsv[:,2].min():.0f}-{bright_hsv[:,2].max():.0f}")

    # ── 4. 保存绿框内区域放大图 ──
    for label, data in [("float_in", data_in), ("float_out", data_out)]:
        roi = data["green_roi"]
        # 放大 10 倍
        big = cv2.resize(roi, (roi.shape[1] * 10, roi.shape[0] * 10), interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(f"{OUTPUT_DIR}/green_roi_{label}.png", big)

    # 差异图
    green_in = data_in["green_roi"]
    green_out = data_out["green_roi"]
    diff_colored = cv2.absdiff(green_in, green_out)
    diff_big = cv2.resize(diff_colored, (diff_colored.shape[1] * 10, diff_colored.shape[0] * 10), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f"{OUTPUT_DIR}/green_roi_diff.png", diff_big)

    print(f"\n放大图已保存到 {OUTPUT_DIR}/")
    print(f"  green_roi_float_in.png   - 绿框区域 x10 (浮标在内)")
    print(f"  green_roi_float_out.png  - 绿框区域 x10 (浮标在外)")
    print(f"  green_roi_diff.png       - 差异图 x10")
    print(f"  bar_profile_*.png        - 滑轨亮度曲线")


if __name__ == "__main__":
    main()
