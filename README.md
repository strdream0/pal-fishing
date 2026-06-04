# 幻兽帕鲁钓鱼助手

基于视觉识别的幻兽帕鲁自动钓鱼工具。Windows Graphics Capture 捕获游戏画面，OpenCV 识别绿框和浮标，Bang-Bang 控制器追踪。

## 功能

- 自动识别钓鱼 UI（绿框、浮标）
- 前探 Bang-Bang 控制器自动追踪
- PySide6 GUI：主窗口、小窗查看、参数调整、热键设置
- 颜色采样向导（截图 → 框选 → 自动填入 HSV）
- 无控制台打包为 EXE

## 使用方法

1. 启动游戏，进入钓鱼
2. 双击 `钓鱼助手.vbs` 或运行 `dist/帕鲁钓鱼助手.exe`
3. 按 F7 打开小窗，F10 开启自动钓鱼
4. 可在参数调整中修改前探时间和阈值

## 热键

| 按键 | 功能 |
|------|------|
| F7 | 开关小窗查看 |
| F8 | 截图 |
| F9 | 开关预览效果 |
| F10 | 开关自动钓鱼 |
| F12 | 开关参数调整 |

## 开发

```bash
uv sync
uv run python fishing.pyw
```

打包：

```bash
uv run pyinstaller fishing.spec
```
