"""
测试游戏物理：单独按/松鼠标，看绿框位移量
用法: uv run python test_physics.py
切到游戏窗口后按键（全局热键，不需要切回终端）:
  F2  - 按20ms松1s  |  F3  - 按50ms松1s  |  F4  - 按100ms松1s
  F5  - 全松1s      |  Esc - 退出
"""
import ctypes
import time

user32 = ctypes.windll.user32

INPUT_MOUSE = 0
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", MOUSEINPUT)]

def send_input(flags):
    inp = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dwFlags=flags))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

def pulse(press_ms, release_ms):
    print(f"\n按 {press_ms}ms 松 {release_ms}ms ...")
    if press_ms > 0:
        send_input(MOUSEEVENTF_LEFTDOWN)
        time.sleep(press_ms / 1000.0)
    send_input(MOUSEEVENTF_LEFTUP)
    time.sleep(release_ms / 1000.0)
    print("  完成。看绿框动了多少像素")

VK_ESC, VK_F2, VK_F3, VK_F4, VK_F5 = 0x1B, 0x71, 0x72, 0x73, 0x74

print("=" * 50)
print("  物理测试: 测量绿框位移 vs 按键时长")
print("=" * 50)
print("  切到游戏 -> 浮标对准绿框中心 -> 按键:")
print("  F2: 按20ms松1s  F3: 按50ms松1s  F4: 按100ms松1s")
print("  F5: 全松1s      Esc: 退出")
print("=" * 50)

prev = {VK_F2: False, VK_F3: False, VK_F4: False, VK_F5: False, VK_ESC: False}
actions = {VK_F2: (20, 1000), VK_F3: (50, 1000), VK_F4: (100, 1000), VK_F5: (0, 1000)}

while True:
    time.sleep(0.05)
    for vk, (press, release) in actions.items():
        cur = (user32.GetAsyncKeyState(vk) & 0x8000) != 0
        if cur and not prev[vk]:
            pulse(press, release)
        prev[vk] = cur

    cur_esc = (user32.GetAsyncKeyState(VK_ESC) & 0x8000) != 0
    if cur_esc and not prev[VK_ESC]:
        break
    prev[VK_ESC] = cur_esc

print("Done.")
