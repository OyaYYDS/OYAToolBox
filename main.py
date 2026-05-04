#!/usr/bin/env python3
"""工具箱启动器 - 主入口"""
import sys
import os

# ── 修复 conda 环境中 icuuc.dll 版本冲突 ──────────────────────────────────────
# conda 的 Library/bin/icuuc.dll 仅导出版本化函数（如 ucnv_open_73），
# 而 Qt6Core.dll 依赖非版本化函数（如 ucnv_open）。
# 必须在导入 PySide6 之前从 PATH 中移除 conda Library 路径，
# 使 Windows 加载系统 System32 的 icuuc.dll（有非版本化导出）。
_path_parts = os.environ.get('PATH', '').split(';')
_filtered = [p for p in _path_parts
             if 'Library\\bin' not in p.replace('/', '\\')
             and 'Library/bin' not in p]
os.environ['PATH'] = ';'.join(_filtered)
os.add_dll_directory('C:\\Windows\\System32')

# 打包后某些机器上 QtWebEngine 可能因沙箱或 GPU 驱动问题出现白屏
if getattr(sys, 'frozen', False):
    os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
    os.environ.setdefault('QT_OPENGL', 'software')
    _flags = os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '').strip()
    _extra = '--disable-gpu --no-sandbox'
    os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = f'{_flags} {_extra}'.strip()
# ─────────────────────────────────────────────────────────────────────────────

# Qt 6 会自动设置 DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2，无需手动调用

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QIcon
import qasync
import asyncio
from pathlib import Path

from app.window import MainWindow


def _resolve_resource(relative_path: str) -> Path:
    candidates: list[Path] = []
    if hasattr(sys, '_MEIPASS'):
        candidates.append(Path(sys._MEIPASS) / relative_path)
    if getattr(sys, 'frozen', False):
        candidates.append(Path(sys.executable).resolve().parent / relative_path)
    candidates.append(Path(__file__).parent / relative_path)

    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def main():
    # 必须在 QApplication 之前设置
    if getattr(sys, 'frozen', False):
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL, True)

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName('工具箱启动器')
    app.setOrganizationName('ToolboxLauncher')
    app.setStyle('Fusion')

    # 设置任务栏 & 窗口图标
    _icon_path = _resolve_resource('OYAToolBoxICO.ico')
    if _icon_path.exists():
        app.setWindowIcon(QIcon(str(_icon_path)))

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == '__main__':
    main()
