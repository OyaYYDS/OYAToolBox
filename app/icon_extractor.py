"""图标提取器 - 纯 ctypes 实现 (shell32 + GDI+), 无 pywin32 / Pillow 依赖

流程: SHGetFileInfoW / ExtractIconExW 获取 HICON (自动解析 .lnk/文件夹/系统关联图标)
      → GDI+ 转换为带 alpha 位图并放大到 48×48
      → 编码 PNG (结果按 路径+mtime 缓存到磁盘)
      → 返回 data URI 字符串

附带图片转换工具: image_to_png / image_to_ico (零依赖, 供生成应用图标用)
"""
import base64
import ctypes
import hashlib
import os
import struct
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Optional, Sequence

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32

SHGFI_ICON = 0x000000100
SHGFI_LARGEICON = 0x000000000
SHGFI_USEFILEATTRIBUTES = 0x000000010

ICON_SIZE = 48


class SHFILEINFOW(ctypes.Structure):
    _fields_ = [
        ('hIcon', wintypes.HANDLE),
        ('iIcon', ctypes.c_int),
        ('dwAttributes', wintypes.DWORD),
        ('szDisplayName', ctypes.c_wchar * 260),
        ('szTypeName', ctypes.c_wchar * 80),
    ]


# ─── GDI+ ─────────────────────────────────────────────────────────────────────

class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', ctypes.c_uint32),
        ('Data2', ctypes.c_uint16),
        ('Data3', ctypes.c_uint16),
        ('Data4', ctypes.c_ubyte * 8),
    ]


CLSID_PNG = GUID(0x557CF406, 0x1A04, 0x11D3, (ctypes.c_ubyte * 8)(0x9A, 0x73, 0x00, 0x00, 0xF8, 0x1E, 0xF3, 0x2E))


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ('GdiplusVersion', ctypes.c_uint32),
        ('DebugEventCallback', ctypes.c_void_p),
        ('SuppressBackgroundThread', ctypes.c_int),
        ('SuppressExternalCodecs', ctypes.c_int),
    ]


_gdiplus_token: Optional[ctypes.c_ulong] = None
_gdiplus_lock = threading.Lock()

PixelFormat32bppPARGB = 0x000E200B
InterpolationModeHighQualityBicubic = 7
PixelOffsetModeHighQuality = 2


def _setup_argtypes(gdip: ctypes.WinDLL):
    """一次性声明 GDI+ 函数签名, 避免默认 ANSI 转换等 ctypes 陷阱"""
    gdip.GdipLoadImageFromFile.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    gdip.GdipCreateBitmapFromHICON.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
    gdip.GdipCreateBitmapFromScan0.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
    ]
    gdip.GdipGetImageWidth.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    gdip.GdipGetImageGraphicsContext.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    gdip.GdipSetInterpolationMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gdip.GdipSetPixelOffsetMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gdip.GdipDrawImageRectI.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ]
    gdip.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
    gdip.GdipDisposeImage.argtypes = [ctypes.c_void_p]
    gdip.GdipSaveImageToFile.argtypes = [
        ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(GUID), ctypes.c_void_p,
    ]


def _gdiplus() -> Optional[ctypes.WinDLL]:
    global _gdiplus_token
    with _gdiplus_lock:
        if _gdiplus_token is None:
            try:
                gdip = ctypes.windll.gdiplus
                inp = GdiplusStartupInput(1, None, 0, 0)
                token = ctypes.c_ulong()
                if gdip.GdiplusStartup(ctypes.byref(token), ctypes.byref(inp), None) != 0:
                    return None
                _gdiplus_token = token
                _setup_argtypes(gdip)
            except Exception:
                return None
        return ctypes.windll.gdiplus


def _image_to_png_bytes(gdip: ctypes.WinDLL, image: ctypes.c_void_p, size: int) -> Optional[bytes]:
    """把 GDI+ 位图高质量缩放到 size×size 并编码为 PNG bytes (不释放传入的 image)"""
    w = ctypes.c_uint()
    gdip.GdipGetImageWidth(image, ctypes.byref(w))
    target = image
    scaled = None
    if w.value != size:
        scaled = ctypes.c_void_p()
        if gdip.GdipCreateBitmapFromScan0(
            size, size, 0, PixelFormat32bppPARGB, None, ctypes.byref(scaled)
        ) != 0 or not scaled:
            return None
        g = ctypes.c_void_p()
        gdip.GdipGetImageGraphicsContext(scaled, ctypes.byref(g))
        gdip.GdipSetInterpolationMode(g, InterpolationModeHighQualityBicubic)
        gdip.GdipSetPixelOffsetMode(g, PixelOffsetModeHighQuality)
        gdip.GdipDrawImageRectI(g, image, 0, 0, size, size)
        gdip.GdipDeleteGraphics(g)
        target = scaled
    try:
        tmp = _cache_dir() / '_tmp_out.png'
        try:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.unlink(missing_ok=True)
            if gdip.GdipSaveImageToFile(target, str(tmp), ctypes.byref(CLSID_PNG), None) != 0:
                return None
            return tmp.read_bytes()
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    finally:
        if scaled:
            gdip.GdipDisposeImage(scaled)


# ─── 公开接口 ─────────────────────────────────────────────────────────────────

def extract_icon(path: str) -> Optional[str]:
    """提取图标, 返回 data URI (image/png 或 image/svg+xml), 失败返回 None"""
    if not path:
        return None

    if path.startswith(('http://', 'https://')):
        return _url_icon_data_uri()

    try:
        png = _load_cached_or_extract(path)
        if not png:
            return None
        return 'data:image/png;base64,' + base64.b64encode(png).decode()
    except Exception:
        return None


def icon_file_to_data_url(path: str) -> Optional[str]:
    """把用户选择的图片/图标文件转为 data URI (对话框自定义图标用)"""
    if not path:
        return None
    ext = Path(path).suffix.lower()
    mime = {
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.bmp': 'image/bmp', '.gif': 'image/gif', '.webp': 'image/webp',
    }.get(ext)
    if mime:
        try:
            return f'data:{mime};base64,' + base64.b64encode(Path(path).read_bytes()).decode()
        except OSError:
            return None
    if ext == '.ico':
        try:
            png = _convert_ico_file(path)
            if png:
                return 'data:image/png;base64,' + base64.b64encode(png).decode()
        except Exception:
            pass
    # 其他文件回退到系统图标提取
    return extract_icon(path)


def image_to_png(src_path: str, dst_path: str, size: int) -> bool:
    """把图片文件缩放为 size×size 的 PNG"""
    gdip = _gdiplus()
    if gdip is None:
        return False
    image = ctypes.c_void_p()
    if gdip.GdipLoadImageFromFile(str(src_path), ctypes.byref(image)) != 0 or not image:
        return False
    try:
        png = _image_to_png_bytes(gdip, image, size)
    finally:
        gdip.GdipDisposeImage(image)
    if not png:
        return False
    try:
        Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
        Path(dst_path).write_bytes(png)
        return True
    except OSError:
        return False


def image_to_ico(src_path: str, dst_path: str,
                 sizes: Sequence[int] = (16, 24, 32, 48, 64, 128, 256)) -> bool:
    """把图片文件转为包含多尺寸 PNG 条目的 .ico (Vista+, 纯标准库)"""
    gdip = _gdiplus()
    if gdip is None:
        return False

    pngs = []
    for size in sizes:
        image = ctypes.c_void_p()
        if gdip.GdipLoadImageFromFile(str(src_path), ctypes.byref(image)) != 0 or not image:
            return False
        try:
            png = _image_to_png_bytes(gdip, image, size)
        finally:
            gdip.GdipDisposeImage(image)
        if not png:
            return False
        pngs.append(png)

    # 打包 ICO: ICONDIR + ICONDIRENTRY[] + PNG 数据
    count = len(pngs)
    header = struct.pack('<HHH', 0, 1, count)
    offset = 6 + 16 * count
    entries = b''
    for i, png in enumerate(pngs):
        field = sizes[i] if sizes[i] < 256 else 0
        entries += struct.pack('<BBBBHHII', field, field, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    try:
        Path(dst_path).write_bytes(header + entries + b''.join(pngs))
        return True
    except OSError:
        return False


# ─── 提取与缓存 ───────────────────────────────────────────────────────────────

def _cache_dir() -> Path:
    base = os.environ.get('LOCALAPPDATA') or os.environ.get('TEMP') or str(Path.home())
    return Path(base) / 'OYAToolBox' / 'icons'


def _cache_path_for(path: str) -> Path:
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0
    key = hashlib.sha1(f'{path}|{mtime}'.encode('utf-8')).hexdigest()[:16]
    return _cache_dir() / f'{key}_{ICON_SIZE}.png'


def _load_cached_or_extract(path: str) -> Optional[bytes]:
    cache_path = _cache_path_for(path)
    if cache_path.exists():
        try:
            return cache_path.read_bytes()
        except OSError:
            pass

    gdip = _gdiplus()
    if gdip is None:
        return None

    hicon = _get_hicon(path)
    if not hicon:
        return None
    try:
        png = _hicon_to_png(gdip, hicon, ICON_SIZE)
    finally:
        user32.DestroyIcon(hicon)

    if png:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(png)
        except OSError:
            pass
    return png


def _get_hicon(path: str) -> Optional[int]:
    """按文件类型选择最合适的取图标方式"""
    p = Path(path)
    ext = p.suffix.lower()

    # .lnk: 解析目标后取目标图标
    if ext == '.lnk':
        target = _lnk_target(path)
        if target and os.path.exists(target):
            hicon = _get_hicon(target)
            if hicon:
                return hicon
        return _get_file_icon_by_attributes(path)

    # 文件夹
    if p.is_dir():
        return _get_folder_hicon(path)

    # 可执行文件/图标库/图标文件: 提取真实图标
    if ext in ('.exe', '.dll', '.scr', '.ico'):
        hicon = _extract_icon_ex(path)
        if hicon:
            return hicon

    # 其他文件: 系统关联图标
    return _get_file_icon_by_attributes(path)


def _extract_icon_ex(path: str) -> Optional[int]:
    """ExtractIconExW 提取 exe/dll/ico 真实图标 (不需要 shell token)"""
    try:
        shell32.ExtractIconExW.argtypes = [
            wintypes.LPCWSTR, ctypes.c_int,
            ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.HICON), wintypes.UINT,
        ]
        large = wintypes.HICON()
        small = wintypes.HICON()
        n = shell32.ExtractIconExW(str(path), 0, ctypes.byref(large), ctypes.byref(small), 1)
        if n <= 0 or not large.value:
            return None
        if small.value:
            user32.DestroyIcon(small)
        return large.value
    except Exception:
        return None


def _get_folder_hicon(path: str) -> Optional[int]:
    """文件夹图标: 优先真实图标, 失败回退属性法 (通用文件夹图标)"""
    hicon = _shgetfileinfo(path, SHGFI_ICON | SHGFI_LARGEICON)
    if hicon:
        return hicon
    return _shgetfileinfo(path, SHGFI_ICON | SHGFI_LARGEICON | SHGFI_USEFILEATTRIBUTES,
                          file_attributes=0x10)  # FILE_ATTRIBUTE_DIRECTORY


def _get_file_icon_by_attributes(path: str) -> Optional[int]:
    """按扩展名取系统关联图标 (不访问文件本身)"""
    return _shgetfileinfo(path, SHGFI_ICON | SHGFI_LARGEICON | SHGFI_USEFILEATTRIBUTES)


def _shgetfileinfo(path: str, flags: int, file_attributes: int = 0) -> Optional[int]:
    try:
        shell32.SHGetFileInfoW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.POINTER(SHFILEINFOW), wintypes.UINT, wintypes.UINT,
        ]
        shell32.SHGetFileInfoW.restype = ctypes.c_size_t
        info = SHFILEINFOW()
        ret = shell32.SHGetFileInfoW(
            str(path), file_attributes, ctypes.byref(info), ctypes.sizeof(info), flags,
        )
        if not ret or not info.hIcon:
            return None
        return info.hIcon
    except Exception:
        return None


def resolve_lnk_target(path: str) -> Optional[str]:
    """解析 .lnk 快捷方式的目标路径 (纯 ctypes IShellLinkW, 无外部依赖)"""
    try:
        ole32 = ctypes.windll.ole32
        # 初始化 COM 公寓 (工作线程/主线程通用, 重复调用返回 S_FALSE 无副作用)
        ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED

        CLSID_ShellLink = GUID(0x00021401, 0, 0, (ctypes.c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))
        IID_IShellLinkW = GUID(0x000214F9, 0, 0, (ctypes.c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))
        IID_IPersistFile = GUID(0x0000010B, 0, 0, (ctypes.c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))

        isl = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_ShellLink), None, 1,  # CLSCTX_INPROC_SERVER
            ctypes.byref(IID_IShellLinkW), ctypes.byref(isl),
        )
        if hr < 0 or not isl:
            return None

        try:
            # 通用 vtable 调用器
            def _call(ptr, index, restype, argtypes, *args):
                vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
                proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
                return proto(vtbl[0][index])(ptr, *args)

            # IPersistFile::Load (vtable index 5)
            ipf = ctypes.c_void_p()
            hr = _call(isl, 0, ctypes.c_long,
                       (ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)),
                       ctypes.byref(IID_IPersistFile), ctypes.byref(ipf))
            if hr < 0 or not ipf:
                return None
            try:
                _call(ipf, 5, ctypes.c_long, (wintypes.LPCWSTR, wintypes.DWORD),
                      str(path), 0)

                # IShellLinkW::GetPath (vtable index 3), SLGP_UNCPRIORITY=2
                buf = ctypes.create_unicode_buffer(1024)
                hr = _call(isl, 3, ctypes.c_long,
                           (wintypes.LPWSTR, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD),
                           buf, 1024, None, 2)
                if hr < 0:
                    return None
                return buf.value or None
            finally:
                _call(ipf, 2, ctypes.c_ulong, ())
        finally:
            _call(isl, 2, ctypes.c_ulong, ())
    except Exception:
        return None


def _lnk_target(path: str) -> Optional[str]:
    return resolve_lnk_target(path)


def _hicon_to_png(gdip: ctypes.WinDLL, hicon: int, size: int) -> Optional[bytes]:
    """HICON → PNG bytes (带 alpha, 放大到指定尺寸)"""
    src = ctypes.c_void_p()
    if gdip.GdipCreateBitmapFromHICON(hicon, ctypes.byref(src)) != 0 or not src:
        return None
    try:
        return _image_to_png_bytes(gdip, src, size)
    finally:
        gdip.GdipDisposeImage(src)


def _convert_ico_file(path: str) -> Optional[bytes]:
    """把 .ico 文件转成 PNG bytes"""
    gdip = _gdiplus()
    if gdip is None:
        return None
    image = ctypes.c_void_p()
    if gdip.GdipLoadImageFromFile(str(path), ctypes.byref(image)) != 0 or not image:
        return None
    try:
        tmp = _cache_dir() / '_tmp_ico.png'
        try:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.unlink(missing_ok=True)
            if gdip.GdipSaveImageToFile(image, str(tmp), ctypes.byref(CLSID_PNG), None) != 0:
                return None
            return tmp.read_bytes()
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
    finally:
        gdip.GdipDisposeImage(image)


def _url_icon_data_uri() -> str:
    """URL 使用默认地球图标 (SVG)"""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">'
        '<circle cx="24" cy="24" r="20" fill="none" stroke="#4a9eff" stroke-width="2.5"/>'
        '<ellipse cx="24" cy="24" rx="9" ry="20" fill="none" stroke="#4a9eff" stroke-width="2"/>'
        '<line x1="4" y1="24" x2="44" y2="24" stroke="#4a9eff" stroke-width="2"/>'
        '<line x1="24" y1="4" x2="24" y2="44" stroke="#4a9eff" stroke-width="2"/>'
        '</svg>'
    )
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()
