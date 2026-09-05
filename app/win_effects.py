"""窗口特效 - DWM 圆角/亚克力 + 原生边缘缩放 (纯 ctypes, 无 pywin32)

pywebview 不暴露 WinForms 窗口句柄, 这里通过 EnumWindows 按进程 ID 定位主窗口。
frameless 窗口边缘缩放: 子类化窗口过程, 拦截 WM_NCHITTEST 在边缘返回 HT* 码,
由系统模态循环接管缩放 (拖动由 pywebview drag region 机制处理)。
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

# 边缘缩放
WM_NCHITTEST = 0x0084
WM_NCLBUTTONDOWN = 0x00A1
GWLP_WNDPROC = -4
HTCLIENT = 1
_HT_CODES = {
    'top': 12, 'bottom': 15, 'left': 10, 'right': 11,
    'topleft': 13, 'topright': 14, 'bottomleft': 16, 'bottomright': 17,
}
EDGE_THRESHOLD = 6  # px, 与前端光标提示一致

WINDOW_TITLE = 'OYAToolBox'

# 子类化回调保活 (必须保持全局引用)
_wndproc_callback = None
_old_wndproc = None


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


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('rcMonitor', wintypes.RECT),
        ('rcWork', wintypes.RECT),
        ('dwFlags', wintypes.DWORD),
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


# ─── 原生边缘缩放 (WM_NCHITTEST 子类化) ───────────────────────────────────────

def _edge_at(x: int, y: int, rect) -> Optional[str]:
    """判断屏幕坐标 (x, y) 是否落在窗口边缘"""
    m = EDGE_THRESHOLD
    near_l = x < rect.left + m
    near_r = x > rect.right - m
    near_t = y < rect.top + m
    near_b = y > rect.bottom - m
    if near_t and near_l:
        return 'topleft'
    if near_t and near_r:
        return 'topright'
    if near_b and near_l:
        return 'bottomleft'
    if near_b and near_r:
        return 'bottomright'
    if near_l:
        return 'left'
    if near_r:
        return 'right'
    if near_t:
        return 'top'
    if near_b:
        return 'bottom'
    return None


def install_resize_support(hwnd: Optional[int]):
    """子类化窗口过程, 让 frameless 窗口支持原生边缘缩放"""
    global _wndproc_callback, _old_wndproc
    if not hwnd or _old_wndproc:
        return

    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.CallWindowProcW.restype = ctypes.c_ssize_t
    user32.CallWindowProcW.argtypes = [
        ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.DefWindowProcW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    ]

    def _cb(hwnd, msg, wparam, lparam):
        # 非客户区按下且命中边缘: 直接交给 DefWindowProc 启动系统缩放循环
        # (WinForms 对无边框窗体会把 WM_NCLBUTTONDOWN 当客户区点击吞掉, 必须绕过)
        if msg == WM_NCLBUTTONDOWN and wparam in _HT_CODES.values():
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        if msg != WM_NCHITTEST:
            return user32.CallWindowProcW(_old_wndproc, hwnd, msg, wparam, lparam)

        ht = user32.CallWindowProcW(_old_wndproc, hwnd, msg, wparam, lparam)
        if ht != HTCLIENT:
            return ht

        # 客户端区域: 命中窗口边缘则交给系统缩放
        x = lparam & 0xFFFF
        if x >= 0x8000:
            x -= 0x10000
        y = (lparam >> 16) & 0xFFFF
        if y >= 0x8000:
            y -= 0x10000

        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return ht
        edge = _edge_at(x, y, rect)
        return _HT_CODES.get(edge, ht)

    proto = ctypes.WINFUNCTYPE(
        ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    )
    _wndproc_callback = proto(_cb)
    _old_wndproc = user32.SetWindowLongPtrW(
        hwnd, GWLP_WNDPROC, ctypes.cast(_wndproc_callback, ctypes.c_void_p).value
    )


def get_window_rect(hwnd: Optional[int]):
    """获取窗口真实外框矩形 (用于关闭时保存精确几何信息)"""
    rect = wintypes.RECT()
    if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    return None


def _get_monitor_work(hwnd: Optional[int]):
    """窗口所在显示器的工作区 (left, top, right, bottom)"""
    rect = wintypes.RECT()
    if not hwnd or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    try:
        mon = user32.MonitorFromRect(ctypes.byref(rect), 2)  # MONITOR_DEFAULTTONEAREST
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(mon, ctypes.byref(mi))
        return mi.rcWork.left, mi.rcWork.top, mi.rcWork.right, mi.rcWork.bottom
    except Exception:
        return None


def set_window_rect(hwnd: Optional[int], x, y, width: int, height: int):
    """一次调用同时设置窗口位置与尺寸 (SWP_NOZORDER | SWP_NOACTIVATE)"""
    if not hwnd:
        return
    user32.SetWindowPos(hwnd, None, int(x), int(y), int(width), int(height), 0x0004 | 0x0010)


def apply_window_geometry(hwnd: Optional[int], x, y, width: int, height: int):
    """强制精确设置窗口外框尺寸

    修复 pywebview 的 WinForms 尺寸坑: FormBorderStyle=None 在 Size 设置之后才应用,
    WinForms 保持客户区尺寸不变导致外框缩小 (少了标准边框的宽高)。
    显示后重新按目标外框尺寸设置一次即可。
    """
    if not hwnd:
        return

    if x is None or y is None:
        # 未指定位置: 按正确尺寸在所在显示器上居中
        work = _get_monitor_work(hwnd)
        if work:
            x = work[0] + (work[2] - work[0] - width) // 2
            y = work[1] + (work[3] - work[1] - height) // 2
        else:
            x, y = 100, 100

    set_window_rect(hwnd, x, y, width, height)
