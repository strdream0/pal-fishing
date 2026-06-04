"""
分析截图：找出绿色框和浮标的颜色范围、坐标
用法: uv run python analyze.py
"""
import os
import cv2
import numpy as np

SCREENSHOT_DIR = "screenshots"
OUTPUT_DIR = "analysis_output"


def find_green_region(bgr):
    """HSV 定位绿色目标区域，返回多个候选供人工确认"""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # 尝试多组绿色阈值
    thresholds = [
        ("窄绿", np.array([45, 100, 80]), np.array([80, 255, 255])),
        ("宽绿", np.array([38, 60, 60]), np.array([88, 255, 255])),
        ("亮绿", np.array([50, 120, 100]), np.array([75, 255, 255])),
    ]

    results = []
    for name, lower, upper in thresholds:
        mask = cv2.inRange(hsv, lower, upper)
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area > 100:
                x, y, w, h = cv2.boundingRect(c)
                candidates.append({
                    "x": x, "y": y, "w": w, "h": h, "area": int(area),
                    "rel_x": f"{x/bgr.shape[1]*100:.1f}%",
                    "rel_y": f"{y/bgr.shape[0]*100:.1f}%",
                    "rel_w": f"{w/bgr.shape[1]*100:.1f}%",
                    "rel_h": f"{h/bgr.shape[0]*100:.1f}%",
                })
        results.append((name, candidates, mask))

    return results


def analyze_float_in_bar(bgr, bar_region):
    """在滑轨区域内分析浮标的颜色特征"""
    bx, by, bw, bh = bar_region
    roi = bgr[by:by+bh, bx:bx+bw]
    roi_hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # 方法1: 白色/高亮 (低饱和度 + 高亮度)
    white_lower = np.array([0, 0, 180])
    white_upper = np.array([180, 50, 255])
    white_mask = cv2.inRange(roi_hsv, white_lower, white_upper)

    # 方法2: 找 ROI 内最亮的区域
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    # 方法3: 边缘检测找浮标轮廓
    edges = cv2.Canny(gray, 50, 150)

    # 方法4: 二值化找显著物体
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

    return {
        "roi_shape": roi.shape,
        "white_mask_contours": _get_contour_info(white_mask),
        "bright_thresh_contours": _get_contour_info(thresh),
        "roi_mean_hsv": {
            "H": f"{roi_hsv[:,:,0].mean():.1f}",
            "S": f"{roi_hsv[:,:,1].mean():.1f}",
            "V": f"{roi_hsv[:,:,2].mean():.1f}",
        },
        "roi_mean_bgr": {
            "B": f"{roi[:,:,0].mean():.1f}",
            "G": f"{roi[:,:,1].mean():.1f}",
            "R": f"{roi[:,:,2].mean():.1f}",
        },
        "white_mask": white_mask,
        "thresh": thresh,
        "edges": edges,
    }


def _get_contour_info(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    infos = []
    for c in contours:
        area = cv2.contourArea(c)
        if area > 15:
            x, y, w, h = cv2.boundingRect(c)
            infos.append({
                "x": x, "y": y, "w": w, "h": h, "area": int(area),
                "cx": x + w // 2, "cy": y + h // 2,
            })
    return infos


def analyze_single_image(filepath):
    """分析单张截图"""
    bgr = cv2.imread(filepath)
    h, w = bgr.shape[:2]
    print(f"\n{'='*60}")
    print(f"图片: {os.path.basename(filepath)}")
    print(f"尺寸: {w} x {h}")
    print(f"{'='*60}")

    # ── 1. 绿色区域检测 ──
    print("\n--- 绿色区域检测 ---")
    green_results = find_green_region(bgr)
    best_candidates = None
    for name, candidates, mask in green_results:
        print(f"\n阈值组 [{name}]: 找到 {len(candidates)} 个绿色候选")
        for i, c in enumerate(candidates):
            print(f"  [{i}] x={c['x']} y={c['y']} w={c['w']} h={c['h']} area={c['area']}")
            print(f"      相对: x={c['rel_x']} y={c['rel_y']} w={c['rel_w']} h={c['rel_h']}")
        if candidates and best_candidates is None:
            best_candidates = candidates

    # 取面积最大的候选作为绿色框
    green_rect = None
    if best_candidates:
        best = max(best_candidates, key=lambda c: c["area"])
        green_rect = (best["x"], best["y"], best["w"], best["h"])
        print(f"\n  => 选定绿色框: x={best['x']} y={best['y']} w={best['w']} h={best['h']}")

    # ── 2. 滑轨区域 ──
    if green_rect:
        gx, gy, gw, gh = green_rect
        bar_margin = int(gw * 2)
        bar_x = max(0, gx - bar_margin)
        bar_y = max(0, gy - int(gh * 0.5))
        bar_w = min(w - bar_x, gw + bar_margin * 2)
        bar_h = min(h - bar_y, int(gh * 3))
        bar_region = (bar_x, bar_y, bar_w, bar_h)
        print(f"\n--- 滑轨区域 ---")
        print(f"  x={bar_x} y={bar_y} w={bar_w} h={bar_h}")
        print(f"  相对: x={bar_x/w*100:.1f}% y={bar_y/h*100:.1f}%")
    else:
        bar_region = (0, 0, w, h)
        print("\n[!] 未找到绿色框，将全图作为搜索范围")

    # ── 3. 浮标分析 ──
    print(f"\n--- 浮标分析 (在滑轨区域内) ---")
    float_info = analyze_float_in_bar(bgr, bar_region)
    print(f"ROI 尺寸: {float_info['roi_shape']}")
    print(f"ROI 平均 HSV: H={float_info['roi_mean_hsv']['H']} S={float_info['roi_mean_hsv']['S']} V={float_info['roi_mean_hsv']['V']}")
    print(f"ROI 平均 BGR: B={float_info['roi_mean_bgr']['B']} G={float_info['roi_mean_bgr']['G']} R={float_info['roi_mean_bgr']['R']}")
    print(f"\n白色候选 (HSV 白色过滤): {len(float_info['white_mask_contours'])} 个")
    for c in float_info['white_mask_contours']:
        print(f"  -> 局部坐标 ({c['x']},{c['y']}) {c['w']}x{c['h']} 中心=({c['cx']},{c['cy']}) 面积={c['area']}")
        abs_cx = bar_region[0] + c['cx']
        abs_cy = bar_region[1] + c['cy']
        print(f"     全局坐标 ({abs_cx},{abs_cy}) 相对=({abs_cx/w*100:.1f}%,{abs_cy/h*100:.1f}%)")

    print(f"\n亮区候选 (阈值200): {len(float_info['bright_thresh_contours'])} 个")
    for c in float_info['bright_thresh_contours']:
        print(f"  -> 局部坐标 ({c['x']},{c['y']}) {c['w']}x{c['h']} 中心=({c['cx']},{c['cy']}) 面积={c['area']}")

    # ── 4. 视图调试图 ──
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    basename = os.path.splitext(os.path.basename(filepath))[0]
    debug = bgr.copy()

    if green_rect:
        gx, gy, gw, gh = green_rect
        cv2.rectangle(debug, (gx, gy), (gx + gw, gy + gh), (0, 255, 0), 2)
        cv2.putText(debug, f"Green({gx},{gy},{gw}x{gh})", (gx, gy - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    bx, by, bw, bh = bar_region
    cv2.rectangle(debug, (bx, by), (bx + bw, by + bh), (255, 255, 0), 1)

    cv2.imwrite(f"{OUTPUT_DIR}/{basename}_debug.png", debug)
    cv2.imwrite(f"{OUTPUT_DIR}/{basename}_white_mask.png", float_info["white_mask"])
    cv2.imwrite(f"{OUTPUT_DIR}/{basename}_bright_thresh.png", float_info["thresh"])
    cv2.imwrite(f"{OUTPUT_DIR}/{basename}_edges.png", float_info["edges"])

    print(f"\n调试图已保存到 {OUTPUT_DIR}/")

    return {
        "file": filepath,
        "size": (w, h),
        "green_rect": green_rect,
        "bar_region": bar_region,
        "float_candidates_white": float_info["white_mask_contours"],
        "float_candidates_bright": float_info["bright_thresh_contours"],
        "roi_mean_hsv": float_info["roi_mean_hsv"],
    }


def main():
    screenshots = [
        os.path.join(SCREENSHOT_DIR, f)
        for f in os.listdir(SCREENSHOT_DIR)
        if f.endswith(".png")
    ]

    if not screenshots:
        print("未找到截图，请将 .png 文件放入 screenshots/")
        return

    print(f"找到 {len(screenshots)} 张截图\n")
    results = []
    for sp in screenshots:
        results.append(analyze_single_image(sp))

    # ── 5. 对比分析 ──
    if len(results) >= 2:
        print(f"\n{'='*60}")
        print("对比分析")
        print(f"{'='*60}")
        r0, r1 = results[0], results[1]
        print(f"\n  {os.path.basename(r0['file'])}:")
        print(f"    绿色框: {r0['green_rect']}")
        print(f"    浮标候选(白): {[(c['cx'],c['cy']) for c in r0['float_candidates_white']]}")
        print(f"    浮标候选(亮): {[(c['cx'],c['cy']) for c in r0['float_candidates_bright']]}")
        print(f"  {os.path.basename(r1['file'])}:")
        print(f"    绿色框: {r1['green_rect']}")
        print(f"    浮标候选(白): {[(c['cx'],c['cy']) for c in r1['float_candidates_white']]}")
        print(f"    浮标候选(亮): {[(c['cx'],c['cy']) for c in r1['float_candidates_bright']]}")


if __name__ == "__main__":
    main()
