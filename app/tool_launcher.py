"""工具启动器 - 负责启动各类工具"""
import os
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional


def launch_tool(tool: dict) -> tuple[bool, str]:
    """
    启动工具，返回 (成功, 错误信息)。
    根据工具类型选择合适的启动方式。
    """
    path = tool.get('path', '').strip()
    args = tool.get('args', '').strip()
    work_dir = tool.get('work_dir', '').strip() or None
    tool_type = tool.get('type', 'file').lower()

    if not path:
        return False, '路径为空'

    # URL 直接用浏览器打开
    if tool_type == 'url' or path.startswith(('http://', 'https://')):
        try:
            webbrowser.open(path)
            return True, ''
        except Exception as e:
            return False, str(e)

    if not os.path.exists(path):
        return False, f'路径不存在: {path}'

    try:
        if tool_type in ('exe', 'lnk', 'file'):
            return _launch_exe(path, args, work_dir)
        if tool_type == 'bat':
            return _launch_script(path, args, work_dir, 'cmd')
        if tool_type == 'cmd':
            return _launch_script(path, args, work_dir, 'cmd')
        if tool_type == 'ps1':
            return _launch_powershell(path, args, work_dir)
        if tool_type == 'folder':
            return _open_folder(path)
        # 通用文件 - 用系统默认程序打开
        return _open_with_default(path)
    except Exception as e:
        return False, str(e)


def _launch_exe(path: str, args: str, work_dir: Optional[str]) -> tuple[bool, str]:
    cmd = f'"{path}"'
    if args:
        cmd += f' {args}'
    cwd = work_dir or str(Path(path).parent)
    subprocess.Popen(cmd, shell=True, cwd=cwd,
                     creationflags=subprocess.DETACHED_PROCESS |
                     subprocess.CREATE_NEW_PROCESS_GROUP)
    return True, ''


def _launch_script(path: str, args: str, work_dir: Optional[str],
                   shell_type: str) -> tuple[bool, str]:
    cwd = work_dir or str(Path(path).parent)
    if shell_type == 'cmd':
        cmd = f'cmd /c "{path}"'
    else:
        cmd = f'"{path}"'
    if args:
        cmd += f' {args}'
    subprocess.Popen(cmd, shell=True, cwd=cwd,
                     creationflags=subprocess.CREATE_NEW_CONSOLE)
    return True, ''


def _launch_powershell(path: str, args: str, work_dir: Optional[str]) -> tuple[bool, str]:
    cwd = work_dir or str(Path(path).parent)
    cmd = f'powershell -ExecutionPolicy Bypass -File "{path}"'
    if args:
        cmd += f' {args}'
    subprocess.Popen(cmd, shell=True, cwd=cwd,
                     creationflags=subprocess.CREATE_NEW_CONSOLE)
    return True, ''


def _open_folder(path: str) -> tuple[bool, str]:
    import ctypes
    ctypes.windll.shell32.ShellExecuteW(None, 'open', path, None, None, 1)
    return True, ''


def _open_with_default(path: str) -> tuple[bool, str]:
    os.startfile(path)
    return True, ''


def open_file_location(path: str) -> tuple[bool, str]:
    """在资源管理器中定位并高亮显示文件"""
    if not path:
        return False, '路径为空'
    if path.startswith(('http://', 'https://', 'ftp://')):
        return False, '网址无法在文件管理器中打开'
    if not os.path.exists(path):
        return False, f'路径不存在: {path}'
    try:
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(
            None, 'open', 'explorer.exe', f'/select,"{path}"', None, 1
        )
        return True, ''
    except Exception:
        try:
            os.startfile(str(Path(path).parent))
            return True, ''
        except Exception as e2:
            return False, str(e2)


def detect_type(path: str) -> str:
    """自动识别文件类型"""
    if path.startswith(('http://', 'https://', 'ftp://')):
        return 'url'
    p = Path(path)
    if not p.exists():
        return 'file'
    if p.is_dir():
        return 'folder'
    ext = p.suffix.lower()
    type_map = {
        '.exe': 'exe', '.dll': 'exe',
        '.bat': 'bat', '.cmd': 'cmd',
        '.ps1': 'ps1', '.psm1': 'ps1',
        '.lnk': 'lnk',
        '.url': 'url',
    }
    return type_map.get(ext, 'file')
