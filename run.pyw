"""无控制台启动器"""
import subprocess, sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.Popen(
    [os.path.join(".venv", "Scripts", "pythonw.exe"), "fishing.pyw"],
    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0x08000000,
    close_fds=True,
)
