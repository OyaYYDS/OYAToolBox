#!/usr/bin/env python3
"""工具箱启动器 - 主入口 (pywebview + WebView2)"""
import json
import os
import sys
from pathlib import Path

import webview

from app.api import Api


def get_resource_path(relative_path: str) -> Path:
    """资源定位: 打包解包目录 -> exe 同目录 -> 源码目录"""
    candidates: list[Path] = []
    if hasattr(sys, '_MEIPASS'):
        candidates.append(Path(sys._MEIPASS) / relative_path)
    if getattr(sys, 'frozen', False):
        candidates.append(Path(sys.executable).resolve().parent / relative_path)
    candidates.append(Path(__file__).resolve().parent / relative_path)

    for path in candidates:
        if path.exists():
            return path
    return candidates[-1]


def main():
    api = Api()
    settings = _json_loads(api.getSettings()) or {}

    html_path = get_resource_path('web/index.html')
    if not html_path.exists():
        raise FileNotFoundError(f'页面文件不存在: {html_path}')

    # 标题栏拖动区: pywebview 内置 drag region 机制 (原生回调移动窗口, 无 Python 往返)
    webview.settings['DRAG_REGION_SELECTOR'] = '#titlebar-drag'

    def _x_or_none(value):
        return value if isinstance(value, int) and value >= 0 else None

    window = webview.create_window(
        title='OYAToolBox',
        url=str(html_path),
        js_api=api,
        width=int(settings.get('window_width', 800)),
        height=int(settings.get('window_height', 600)),
        x=_x_or_none(settings.get('window_x')),
        y=_x_or_none(settings.get('window_y')),
        min_size=(800, 500),
        frameless=True,
        easy_drag=False,          # 关闭整窗拖动, 防止与工具项拖拽排序冲突
        on_top=bool(settings.get('always_on_top', False)),
        # 不透明窗口: 页面用 CSS 填满背景, 圆角由 DWM 处理 (避免 transparent=True
        # 导致窗体白色背景从页面圆角处透出的问题)
        transparent=False,
        background_color=_resolve_window_bg(settings),
        text_select=False,
    )

    api.attach_window(window)
    api.set_desired_geometry(
        _x_or_none(settings.get('window_x')),
        _x_or_none(settings.get('window_y')),
        int(settings.get('window_width', 800)),
        int(settings.get('window_height', 600)),
    )
    window.events.shown += api.on_window_shown
    window.events.closing += api.on_window_closing

    # OS 文件拖入: 注册 body drop 监听 (pywebview DOM API 自动配对完整文件路径)
    from webview.dom import DOMEventHandler

    def _register_drop():
        try:
            window.dom.body.events.drop += DOMEventHandler(
                api.on_files_dropped, prevent_default=True
            )
        except Exception:
            pass

    window.events.loaded += _register_drop

    icon_path = get_resource_path('OYAToolBoxICO.ico')
    webview.start(
        gui='edgechromium',
        debug=os.environ.get('OYA_DEBUG') == '1',
        icon=str(icon_path),
    )


def _json_loads(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def _resolve_window_bg(settings: dict) -> str:
    """按主题解析窗口底色 (页面 CSS 加载前避免白闪/黑闪)"""
    theme = settings.get('theme', 'dark')
    if theme == 'system':
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize',
            )
            theme = 'dark' if winreg.QueryValueEx(key, 'AppsUseLightTheme')[0] == 0 else 'light'
        except Exception:
            theme = 'dark'
    return '#0c0c12' if theme == 'dark' else '#f0f2f8'


if __name__ == '__main__':
    main()
