"""
幻兽帕鲁钓鱼 v4 — GUI主窗口 + 动态热键 + 可调颜色
用法: uv run python fishing.py
"""
import os, sys, time, threading, ctypes
from ctypes import wintypes

import cv2, numpy as np
import windows_capture as wc, mss

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from controller import BangBangController
from ui.preview import PreviewWindow
from ui.result import ResultWindow
from ui.params import ParamsWindow
from ui.mainwin import MainWindow
from ui.hotkeys import HotkeyWindow, DEFAULT_KEYS

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

def get_window_rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom

def get_window_process_name(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x0400|0x0010, False, pid.value)
    if not h: return ""
    n = ctypes.create_unicode_buffer(260)
    psapi.GetModuleBaseNameW(h, None, n, ctypes.sizeof(n))
    kernel32.CloseHandle(h)
    return n.value

def get_window_title(hwnd):
    l = user32.GetWindowTextLengthW(hwnd)
    if l==0: return ""
    b = ctypes.create_unicode_buffer(l+1)
    user32.GetWindowTextW(hwnd, b, l+1)
    return b.value

def find_palworld_window():
    results=[]
    def cb(hwnd,_):
        if not user32.IsWindowVisible(hwnd): return True
        p=get_window_process_name(hwnd)
        if "palworld" in p.lower():
            x1,y1,x2,y2=get_window_rect(hwnd); w,h=x2-x1,y2-y1
            if w>200 and h>200:
                results.append({"hwnd":hwnd,"title":get_window_title(hwnd),
                                "process":p,"left":x1,"top":y1,"width":w,"height":h})
        return True
    user32.EnumWindows(WNDENUMPROC(cb),0)
    if results:
        g=[r for r in results if "shipping" in r["process"].lower()]
        if g: results=g
        results.sort(key=lambda r:r["width"]*r["height"],reverse=True)
    return results[0] if results else None

# ── 识别 (支持动态颜色) ──
BAR_X1,BAR_Y1=34.2,27.4; BAR_X2,BAR_Y2=66.5,35.3
_last_float_x=None
_current_colors = None

def set_detect_colors(c):
    global _current_colors
    _current_colors = c

def detect(bgr):
    global _last_float_x, _current_colors
    h,w=bgr.shape[:2]
    bx1,by1=int(w*BAR_X1/100),int(h*BAR_Y1/100)
    bx2,by2=int(w*BAR_X2/100),int(h*BAR_Y2/100)
    bar=bgr[by1:by2,bx1:bx2,:]
    hsv=cv2.cvtColor(bar,cv2.COLOR_BGR2HSV)
    bh,bs,bv=hsv[:,:,0],hsv[:,:,1],hsv[:,:,2]

    # 绿框颜色 (可动态调整)
    c = _current_colors or {}
    g_hl, g_hh = c.get("green_h_lo", 58), c.get("green_h_hi", 87)
    g_sl, g_vl = c.get("green_s_lo", 110), c.get("green_v_lo", 220)

    gp=(bh>g_hl)&(bh<g_hh)&(bs>g_sl)&(bv>g_vl)
    cr=np.mean(gp,axis=0); ig=cr>0.04
    ed=np.diff(np.concatenate([[0],ig.astype(int),[0]]))
    st,en=np.where(ed==1)[0],np.where(ed==-1)[0]
    gr=None
    segs=[(s,e) for s,e in zip(st,en) if e-s>10]
    if segs:
        mg=[segs[0]]
        for s,e in segs[1:]:
            ps,pe=mg[-1]
            if s-pe<40: mg[-1]=(ps,e)
            else: mg.append((s,e))
        s,e=max(mg,key=lambda x:x[1]-x[0])
        rr=np.mean(gp[:,s:e],axis=1); rs=np.where(rr>0.02)[0]
        gy1=by1+rs[0] if len(rs)>0 else by1
        gy2=by1+rs[-1]+1 if len(rs)>0 else by2
        gr=(bx1+s,gy1,e-s,gy2-gy1)

    # 浮标颜色 (可动态调整)
    f_hl, f_hh = c.get("float_h_lo", 20), c.get("float_h_hi", 32)
    f_sl, f_vl = c.get("float_s_lo", 105), c.get("float_v_lo", 237)

    fl=np.array([f_hl,f_sl,f_vl]); fu=np.array([f_hh,255,255])
    fm=cv2.inRange(hsv,fl,fu)
    fm=cv2.morphologyEx(fm,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    fc,_=cv2.findContours(fm,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    fp=None; cands=[]
    for c in sorted(fc,key=cv2.contourArea,reverse=True)[:3]:
        if cv2.contourArea(c)>15:
            fx,fy,fw,fh=cv2.boundingRect(c)
            cands.append((bx1+fx+fw//2,by1+fy+fh//2))
    if cands:
        if _last_float_x is not None and len(cands)>1:
            close=[p for p in cands if abs(p[0]-_last_float_x)<100]
            fp=close[0] if close else cands[0]
        else: fp=cands[0]
        _last_float_x=fp[0]

    result="?"
    if gr and fp:
        gx,gy,gw,gh=gr; fx,fy=fp
        if fx<gx-12: result="LEFT"
        elif fx>gx+gw+12: result="RIGHT"
        else: result="IN"
    return gr,fp,result,(bx1,by1,bx2,by2)

# ── 主函数 ──
def main():
    global _current_colors
    os.makedirs("screenshots",exist_ok=True)
    win=find_palworld_window()
    if not win: sys.exit(1)
    app=QApplication(sys.argv)
    preview=PreviewWindow()
    result_win=ResultWindow(win["left"],win["top"])
    controller=BangBangController(lookahead_ms=100,threshold=15)
    params_win=ParamsWindow(controller)
    # 热键
    key_actions = dict(DEFAULT_KEYS)
    hotkeys_win=HotkeyWindow(on_change=lambda a,v: key_actions.__setitem__(a,v))
    control_enabled = False

    def toggle_auto():
        nonlocal control_enabled
        control_enabled = not control_enabled
        main_win.set_auto_status(control_enabled)
        if not control_enabled: controller.stop()

    running = True
    def shutdown():
        nonlocal running
        running = False
        controller.stop()
        preview.close()
        result_win.close()
        params_win.close()
        hotkeys_win.close()

    main_win=MainWindow(preview.toggle,result_win.toggle,
                         params_win.toggle,hotkeys_win.toggle,toggle_auto)
    main_win.set_shutdown(shutdown)
    main_win.show()

    # 颜色动态绑定
    _current_colors = params_win.get_colors()
    def on_color_change(colors):
        global _current_colors
        _current_colors = colors
        set_detect_colors(colors)

    params_win.set_on_color_change(on_color_change)

    class FB:
        def __init__(s): s.l=threading.Lock(); s.f=None; s.r=False
        def put(s,f):
            with s.l: s.f=f; s.r=True
        def get(s):
            with s.l: return s.f.copy() if s.r else None

    fb=FB()
    def on_frame_arrived(f,c):
        try:
            bgra=f.frame_buffer
            if bgra is not None: fb.put(cv2.cvtColor(bgra,cv2.COLOR_BGRA2BGR))
        except: pass
    def on_closed(): pass

    cap=wc.WindowsCapture(cursor_capture=False,draw_border=False,window_hwnd=win["hwnd"])
    cap.event(on_frame_arrived); cap.event(on_closed)
    try:
        t=threading.Thread(target=cap.start,daemon=True); t.start()
        time.sleep(0.5)
        if not t.is_alive(): raise RuntimeError("WGC fail")
        mode="WGC"
    except Exception:
        mode="MSS"
        mode="MSS"; sct=mss.mss()
        region={"left":win["left"],"top":win["top"],"width":win["width"],"height":win["height"]}

    all_vks = set(key_actions.values())
    prev = {vk: False for vk in all_vks}
    shot_cnt = 0
    last_shot = 0.0

    while running:
        now = time.time()

        all_vks = set(key_actions.values())
        for vk in all_vks:
            if vk not in prev:
                prev[vk] = False
        cur = {vk: (user32.GetAsyncKeyState(vk) & 0x8000) != 0 for vk in all_vks}

        vk_to_action = {v: k for k, v in key_actions.items()}

        for vk, cur_val in cur.items():
            if cur_val and not prev.get(vk, False):
                action = vk_to_action.get(vk)
                if action == "小窗查看":
                    result_win.toggle()
                elif action == "截图" and now - last_shot > 0.3:
                    last_shot = now; shot_cnt += 1
                    cv2.imwrite(f"screenshots/shot_{shot_cnt:03d}.png", frame)
                elif action == "预览效果":
                    preview.toggle()
                elif action == "自动钓鱼":
                    control_enabled = not control_enabled
                    main_win.set_auto_status(control_enabled)
                    if not control_enabled: controller.stop()
                elif action == "参数调整":
                    params_win.toggle()

        for vk in all_vks:
            prev[vk] = cur[vk]

        # 捕获
        if mode == "WGC":
            frame = fb.get()
            if frame is None: time.sleep(0.005); continue
        else:
            frame = cv2.cvtColor(np.array(sct.grab(region)), cv2.COLOR_BGRA2BGR)

        # 识别
        gr, fp, result, br = detect(frame)

        # 控制
        if control_enabled:
            controller.update(gr, fp, now)

        # UI
        preview.show(frame, gr, fp, br, result, control_enabled, controller)
        preview.check_close()
        result_win.show(gr, fp, result, control_enabled)
        app.processEvents()

        time.sleep(0.005)

if __name__ == "__main__":
    main()
