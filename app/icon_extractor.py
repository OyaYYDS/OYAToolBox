"""图标提取器 - 从各类文件提取图标并转为 base64 PNG"""
import os
import io
import base64
import threading
from pathlib import Path
from typing import Optional

try:
    import win32gui
    import win32ui
    import win32con
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

try:
    import win32com.client
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

_shell_lock = threading.Lock()


def extract_icon(path: str) -> Optional[str]:
    """从路径提取图标，返回 base64 PNG 字符串，失败返回 None"""
    if not path:
        return None

    if path.startswith(('http://', 'https://')):
        return _url_icon()

    p = Path(path)
    ext = p.suffix.lower()

    try:
        if ext == '.lnk':
            return _extract_lnk_icon(path)
        if ext == '.ico':
            return _load_ico_file(path)
        if ext in ('.exe', '.dll', '.scr'):
            return _extract_file_icon(path)
        if p.is_dir():
            return _extract_folder_icon(path)
        # 其他文件尝试系统关联图标
        return _extract_file_icon(path)
    except Exception:
        return None


def _extract_file_icon(path: str, size: int = 48) -> Optional[str]:
    """使用双背景法提取带 alpha 的图标"""
    if not WIN32_AVAILABLE or not PIL_AVAILABLE:
        return None
    try:
        large, small = win32gui.ExtractIconEx(path, 0, 1)
        hicon = None
        other = []
        if large:
            hicon = large[0]
            other.extend(large[1:])
        if small:
            if hicon is None:
                hicon = small[0]
                other.extend(small[1:])
            else:
                other.extend(small)

        if hicon is None:
            return None

        result = _hicon_to_base64(hicon, size)

        win32gui.DestroyIcon(hicon)
        for h in other:
            try:
                win32gui.DestroyIcon(h)
            except Exception:
                pass
        return result
    except Exception:
        return None


def _hicon_to_base64(hicon, size: int = 48) -> Optional[str]:
    """双背景法：分别在黑白背景上绘制图标，还原真实 alpha 通道"""
    if not WIN32_AVAILABLE or not PIL_AVAILABLE:
        return None
    try:
        hdc_screen = win32gui.GetDC(0)
        hdc = win32ui.CreateDCFromHandle(hdc_screen)
        hdc_black = hdc.CreateCompatibleDC()
        hdc_white = hdc.CreateCompatibleDC()

        bmp_black = win32ui.CreateBitmap()
        bmp_white = win32ui.CreateBitmap()
        bmp_black.CreateCompatibleBitmap(hdc, size, size)
        bmp_white.CreateCompatibleBitmap(hdc, size, size)

        hdc_black.SelectObject(bmp_black)
        hdc_white.SelectObject(bmp_white)

        # 黑色背景
        hdc_black.FillSolidRect((0, 0, size, size), 0x000000)
        win32gui.DrawIconEx(hdc_black.GetSafeHdc(), 0, 0, hicon,
                            size, size, 0, None, win32con.DI_NORMAL)

        # 白色背景
        hdc_white.FillSolidRect((0, 0, size, size), 0xFFFFFF)
        win32gui.DrawIconEx(hdc_white.GetSafeHdc(), 0, 0, hicon,
                            size, size, 0, None, win32con.DI_NORMAL)

        data_black = bmp_black.GetBitmapBits(True)
        data_white = bmp_white.GetBitmapBits(True)

        win32gui.ReleaseDC(0, hdc_screen)
        del hdc_black, hdc_white, bmp_black, bmp_white, hdc

        img_b = Image.frombuffer('RGBA', (size, size), data_black, 'raw', 'BGRA', 0, 1)
        img_w = Image.frombuffer('RGBA', (size, size), data_white, 'raw', 'BGRA', 0, 1)

        result = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        pb = img_b.load()
        pw = img_w.load()
        pr = result.load()

        for y in range(size):
            for x in range(size):
                rb, gb, bb, _ = pb[x, y]
                rw, gw, bw, _ = pw[x, y]
                alpha = 255 - max(rw - rb, gw - gb, bw - bb, 0)
                if alpha > 0:
                    r = min(int(rb * 255 / alpha), 255)
                    g = min(int(gb * 255 / alpha), 255)
                    b = min(int(bb * 255 / alpha), 255)
                    pr[x, y] = (r, g, b, alpha)
                else:
                    pr[x, y] = (0, 0, 0, 0)

        buf = io.BytesIO()
        result.save(buf, 'PNG')
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _extract_lnk_icon(lnk_path: str) -> Optional[str]:
    """解析 .lnk 快捷方式，提取目标图标"""
    if not WIN32COM_AVAILABLE:
        return None
    try:
        with _shell_lock:
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            target = shortcut.Targetpath
            icon_loc = shortcut.IconLocation  # "path,index"

        icon_path = icon_loc.split(',')[0].strip() if icon_loc else ''
        if icon_path and os.path.exists(icon_path):
            result = _extract_file_icon(icon_path)
            if result:
                return result
        if target and os.path.exists(target):
            return _extract_file_icon(target)
    except Exception:
        pass
    return None


def _extract_folder_icon(path: str) -> Optional[str]:
    """提取文件夹图标"""
    if not WIN32_AVAILABLE or not PIL_AVAILABLE:
        return None
    try:
        SHGFI_ICON = 0x000000100
        SHGFI_LARGEICON = 0x000000000

        class SHFILEINFO(ctypes.Structure):
            _fields_ = [
                ('hIcon', ctypes.c_void_p),
                ('iIcon', ctypes.c_int),
                ('dwAttributes', ctypes.c_uint32),
                ('szDisplayName', ctypes.c_char * 260),
                ('szTypeName', ctypes.c_char * 80),
            ]

        import ctypes
        info = SHFILEINFO()
        ret = ctypes.windll.shell32.SHGetFileInfoW(
            path, 0, ctypes.byref(info), ctypes.sizeof(info),
            SHGFI_ICON | SHGFI_LARGEICON
        )
        if ret and info.hIcon:
            hicon = win32gui.CreateIconFromResourceEx(
                b'', False, 0x00030000, 48, 48, win32con.LR_DEFAULTCOLOR
            )
            # Use the hIcon directly
            result = _hicon_to_base64(info.hIcon, 48)
            win32gui.DestroyIcon(info.hIcon)
            return result
    except Exception:
        pass
    return None


def _load_ico_file(path: str) -> Optional[str]:
    """直接加载 .ico 文件"""
    if not PIL_AVAILABLE:
        return None
    try:
        img = Image.open(path)
        # 选择最大尺寸
        if hasattr(img, 'ico'):
            sizes = img.ico.sizes()
            if sizes:
                best = max(sizes, key=lambda s: s[0] * s[1])
                img.size = best
        img = img.convert('RGBA').resize((48, 48), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _url_icon() -> Optional[str]:
    """URL 使用默认地球图标（SVG 转 base64）"""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">'
        '<circle cx="24" cy="24" r="20" fill="none" stroke="#4a9eff" stroke-width="2.5"/>'
        '<ellipse cx="24" cy="24" rx="9" ry="20" fill="none" stroke="#4a9eff" stroke-width="2"/>'
        '<line x1="4" y1="24" x2="44" y2="24" stroke="#4a9eff" stroke-width="2"/>'
        '<line x1="24" y1="4" x2="24" y2="44" stroke="#4a9eff" stroke-width="2"/>'
        '</svg>'
    )
    return 'svg:' + base64.b64encode(svg.encode()).decode()


def generate_text_icon(text: str, color: str = '#4a9eff',
                       bg_alpha: int = 200, size: int = 48) -> Optional[str]:
    """生成文字图标，返回 base64 PNG"""
    if not PIL_AVAILABLE:
        return None
    try:
        abbr = text[:2].upper() if len(text) >= 2 else text.upper()
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 圆角背景
        draw.rounded_rectangle((2, 2, size - 2, size - 2),
                                radius=10, fill=(r, g, b, bg_alpha))

        # 文字
        font_size = size // 2
        try:
            font = ImageFont.truetype('arial.ttf', font_size)
        except Exception:
            try:
                font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', font_size)
            except Exception:
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), abbr, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = (size - tw) // 2 - bbox[0]
        ty = (size - th) // 2 - bbox[1]
        draw.text((tx, ty), abbr, fill=(255, 255, 255, 240), font=font)

        buf = io.BytesIO()
        img.save(buf, 'PNG')
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None
