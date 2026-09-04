"""窗口特效 - DWM 圆角/亚克力 (纯 ctypes, 无 pywin32)

pywebview 不暴露 WinForms 窗口句柄, 这里通过 EnumWindows 按进程 ID 定位主窗口。
窗口拖动/缩放由 pywebview 内置机制处理 (drag region + frameless 边缘缩放)。
"""
import ctypes
import os
from ctypes import wintypes
from typing import Optional

user32 = ctypes.windll.user32

# DWM 常量
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWCP_ROUND = 2
DWMSBT_TRANSIENTWINDOW = 3   # Acrylic
WCA_ACCENT_POLICY = 19
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4

WINDOW_TITLE = 'OYAToolBox'


class _MARGINS(ctypes.Structure):
    _fields_ = [
        ('cxLeftWidth', ctypes.c_int),
        ('cxRightWidth', ctypes.c_int),
        ('cyTopHeight', ctypes.c_int),
        ('cyBottomHeight', ctypes.c_int),
    ]


class _ACCENTPOLICY(ctypes.Structure):
    _fields_ = [
        ('AccentState', ctypes.c_int),
        ('AccentFlags', ctypes.c_int),
        ('GradientColor', ctypes.c_uint),
        ('AnimationId', ctypes.c_int),
    ]


class _WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [
        ('Attribute', ctypes.c_int),
        ('Data', ctypes.c_void_p),
        ('SizeOfData', ctypes.c_size_t),
    ]


# ─── 窗口句柄定位 ─────────────────────────────────────────────────────────────

def find_main_hwnd(pid: Optional[int] = None) -> Optional[int]:
    """定位本进程的主窗口句柄 (优先匹配窗口标题)"""
    pid = pid or os.getpid()
    found = []

    def _cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid:
                n = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                found.append((hwnd, buf.value))
        return True

    _cb_proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(_cb_proto(_cb), 0)

    for hwnd, title in found:
        if title == WINDOW_TITLE:
            return hwnd
    return found[0][0] if found else None


# ─── 窗口特效 ─────────────────────────────────────────────────────────────────

def apply_window_effects(hwnd: Optional[int]):
    if not hwnd:
        return
    _apply_round_corners(hwnd)
    _apply_acrylic(hwnd)


def _apply_round_corners(hwnd: int):
    try:
        val = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(val), ctypes.sizeof(val),
        )
    except Exception:
        pass


def _apply_acrylic(hwnd: int):
    """Windows 11 亚克力, 回落 Windows 10 SetWindowCompositionAttribute"""
    applied = False
    try:
        val = ctypes.c_int(DWMSBT_TRANSIENTWINDOW)
        r = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(val), ctypes.sizeof(val),
        )
        if r == 0:
            applied = True
            m = _MARGINS(-1, -1, -1, -1)
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))
    except Exception:
        pass

    if not applied:
        try:
            accent = _ACCENTPOLICY()
            accent.AccentState = ACCENT_ENABLE_ACRYLICBLURBEHIND
            accent.GradientColor = 0xCC101014  # 深色半透明
            accent.AccentFlags = 0x02          # 边框颜色

            data = _WINDOWCOMPOSITIONATTRIBDATA()
            data.Attribute = WCA_ACCENT_POLICY
            data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
            data.SizeOfData = ctypes.sizeof(accent)

            user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        except Exception:
            pass
