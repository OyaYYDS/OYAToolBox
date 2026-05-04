"""主窗口 - 无边框、毛玻璃、透明背景的 PySide6 窗口"""
import ctypes
import ctypes.wintypes
import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QUrl

from .bridge import Bridge
from .data_manager import DataManager


# ─── Windows DWM 常量 ─────────────────────────────────────────────────────────
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWCP_ROUND = 2
DWMSBT_TRANSIENTWINDOW = 3   # Acrylic
DWMSBT_MAINWINDOW = 2        # Mica
WCA_ACCENT_POLICY = 19
ACCENT_ENABLE_ACRYLICBLURBEHIND = 4


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


class DroppableWebView(QWebEngineView):
    """支持文件拖拽的 WebEngine 视图"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._bridge: Bridge | None = None

    def set_bridge(self, bridge: Bridge):
        self._bridge = bridge

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if paths and self._bridge:
                self._bridge.notify_files_dropped(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._data_manager = DataManager()
        settings = self._data_manager.get_settings()

        # 无边框 + 透明背景
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 窗口图标
        _icon_path = Path(__file__).parent.parent / '图标.ico'
        if _icon_path.exists():
            self.setWindowIcon(QIcon(str(_icon_path)))

        # 窗口尺寸
        w = settings.get('window_width', 1200)
        h = settings.get('window_height', 800)
        self.resize(w, h)

        x = settings.get('window_x', -1)
        y = settings.get('window_y', -1)
        if x >= 0 and y >= 0:
            self.move(x, y)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(
                (screen.width() - w) // 2,
                (screen.height() - h) // 2
            )

        self._setup_ui()

        # 窗口显示后应用 DWM 效果
        QTimer.singleShot(150, self._apply_dwm_effect)

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # WebEngine 视图
        self._web_view = DroppableWebView(self)
        self._web_view.setStyleSheet('background: transparent;')
        layout.addWidget(self._web_view)

        # QWebChannel
        self._bridge = Bridge(self, self._data_manager)
        self._web_view.set_bridge(self._bridge)
        self._channel = QWebChannel()
        self._channel.registerObject('bridge', self._bridge)

        page = self._web_view.page()
        page.setWebChannel(self._channel)
        page.setBackgroundColor(QColor(Qt.GlobalColor.transparent))

        # 启用必要的 WebEngine 功能
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.DnsPrefetchEnabled, False)

        # 连接桥接信号
        self._bridge.windowMoveRequest.connect(self._on_move)
        self._bridge.windowResizeRequest.connect(self._on_resize)
        self._bridge.windowMinimizeRequest.connect(self.showMinimized)
        self._bridge.windowCloseRequest.connect(self._save_and_close)
        self._bridge.windowAlwaysOnTopRequest.connect(self._set_always_on_top)

        # 加载主页面
        html_path = Path(__file__).parent.parent / 'web' / 'index.html'
        self._web_view.load(QUrl.fromLocalFile(str(html_path)))

    # ─── 窗口效果 ─────────────────────────────────────────────────────────────

    def _apply_dwm_effect(self):
        try:
            hwnd = int(self.winId())
            self._apply_acrylic_win11(hwnd)
        except Exception as e:
            print(f'[DWM] 效果应用失败: {e}')

    def _apply_acrylic_win11(self, hwnd: int):
        """Windows 11 亚克力效果"""
        try:
            # 圆角
            val = ctypes.c_int(DWMWCP_ROUND)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
                ctypes.byref(val), ctypes.sizeof(val)
            )
        except Exception:
            pass

        # 尝试 Windows 11 22H2+ Acrylic
        applied = False
        try:
            val = ctypes.c_int(DWMSBT_TRANSIENTWINDOW)
            r = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA_SYSTEMBACKDROP_TYPE,
                ctypes.byref(val), ctypes.sizeof(val)
            )
            if r == 0:
                applied = True
                # 扩展框架到整个窗口
                m = _MARGINS(-1, -1, -1, -1)
                ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(m))
        except Exception:
            pass

        # 回落到 Windows 10 SetWindowCompositionAttribute
        if not applied:
            try:
                accent = _ACCENTPOLICY()
                accent.AccentState = ACCENT_ENABLE_ACRYLICBLURBEHIND
                accent.GradientColor = 0xCC101014  # 深色半透明
                accent.AccentFlags = 0x02  # 边框颜色

                data = _WINDOWCOMPOSITIONATTRIBDATA()
                data.Attribute = WCA_ACCENT_POLICY
                data.Data = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
                data.SizeOfData = ctypes.sizeof(accent)

                ctypes.windll.user32.SetWindowCompositionAttribute(
                    hwnd, ctypes.byref(data)
                )
            except Exception:
                pass

    # ─── 槽函数 ───────────────────────────────────────────────────────────────

    @Slot(int, int)
    def _on_move(self, dx: int, dy: int):
        pos = self.pos()
        self.move(pos.x() + dx, pos.y() + dy)

    @Slot(int, int)
    def _on_resize(self, width: int, height: int):
        self.resize(max(width, 800), max(height, 500))
        QTimer.singleShot(50, self._apply_dwm_effect)

    @Slot(bool)
    def _set_always_on_top(self, on_top: bool):
        flags = self.windowFlags()
        if on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        QTimer.singleShot(50, self._apply_dwm_effect)

    def _save_and_close(self):
        settings = self._data_manager.get_settings()
        settings['window_x'] = self.x()
        settings['window_y'] = self.y()
        settings['window_width'] = self.width()
        settings['window_height'] = self.height()
        self._data_manager.save_settings(settings)
        self.close()
