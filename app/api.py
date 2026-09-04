"""js_api 桥接 - pywebview 后端 API (与旧 QWebChannel Bridge 保持同一接口)

- 数据方法: 同步返回 JSON 字符串, 前端 await 调用
- 图标提取: 提交线程池异步执行, 完成后通过 evaluate_js 推送 iconLoaded
"""
import ctypes
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .data_manager import DataManager
from .icon_extractor import extract_icon, icon_file_to_data_url
from .tool_launcher import launch_tool, open_file_location, detect_type
from . import win_effects

user32 = ctypes.windll.user32


class Api:
    """暴露给前端的 API 对象 (pywebview js_api)

    注意: 方法名前缀不含下划线即会被 pywebview 暴露给 JS;
    下划线开头的属性和方法不会暴露。
    """

    def __init__(self):
        self._dm = DataManager()
        self._window = None
        self._hwnd = None
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix='icon')
        self._last_dialog_dir = ''

    # ─── 窗口生命周期 (供 main.py 调用) ───────────────────────────────────────

    def attach_window(self, window):
        self._window = window

    def on_window_shown(self):
        self._hwnd = win_effects.find_main_hwnd(os.getpid())
        win_effects.apply_window_effects(self._hwnd)

    def on_window_closing(self):
        """关闭前保存窗口几何信息"""
        try:
            w = self._window
            settings = self._dm.get_settings()
            settings['window_x'] = int(w.x or 0)
            settings['window_y'] = int(w.y or 0)
            settings['window_width'] = int(w.width)
            settings['window_height'] = int(w.height)
            self._dm.save_settings(settings)
        except Exception:
            pass

    # ─── 工具 CRUD ────────────────────────────────────────────────────────────

    def getTools(self) -> str:
        return json.dumps(self._dm.get_tools(), ensure_ascii=False)

    def addTool(self, tool_json: str) -> str:
        try:
            tool = json.loads(tool_json)
            saved = self._dm.add_tool(tool)
            self._push_tools_updated()
            return json.dumps({'ok': True, 'tool': saved}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)

    def updateTool(self, tool_id: str, updates_json: str) -> str:
        try:
            updates = json.loads(updates_json)
            result = self._dm.update_tool(tool_id, updates)
            if result:
                self._push_tools_updated()
                return json.dumps({'ok': True, 'tool': result}, ensure_ascii=False)
            return json.dumps({'ok': False, 'error': '工具不存在'}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)

    def deleteTool(self, tool_id: str) -> str:
        ok = self._dm.delete_tool(tool_id)
        if ok:
            self._push_tools_updated()
        return json.dumps({'ok': ok}, ensure_ascii=False)

    def reorderTools(self, ids_json: str) -> str:
        try:
            ids = json.loads(ids_json)
            self._dm.reorder_tools(ids)
            return json.dumps({'ok': True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)

    def launchTool(self, tool_id: str) -> str:
        tool = self._dm.get_tool(tool_id)
        if not tool:
            return json.dumps({'ok': False, 'error': '工具不存在'}, ensure_ascii=False)
        ok, err = launch_tool(tool)
        if ok:
            self._dm.record_usage(tool_id)
        return json.dumps({'ok': ok, 'error': err}, ensure_ascii=False)

    # ─── 图标 ─────────────────────────────────────────────────────────────────

    def requestIcon(self, tool_id: str, path: str):
        """异步提取图标, 完成后通过 iconLoaded 推回前端"""
        self._executor.submit(self._icon_worker, tool_id, path)

    def _icon_worker(self, tool_id: str, path: str):
        try:
            data = extract_icon(path)
        except Exception:
            data = None
        self._push('iconLoaded', tool_id, data or '')

    def extractIconSync(self, path: str) -> str:
        """同步转换图标 (对话框预览用): 返回 data URI"""
        try:
            return icon_file_to_data_url(path) or ''
        except Exception:
            return ''

    # ─── 设置 / 分类 ──────────────────────────────────────────────────────────

    def getSettings(self) -> str:
        return json.dumps(self._dm.get_settings(), ensure_ascii=False)

    def saveSettings(self, settings_json: str) -> str:
        try:
            settings = json.loads(settings_json)
            self._dm.save_settings(settings)
            self._push('settingsUpdated',
                       json.dumps(self._dm.get_settings(), ensure_ascii=False))
            return json.dumps({'ok': True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)

    def getCategories(self) -> str:
        return json.dumps(self._dm.get_categories(), ensure_ascii=False)

    def addCategory(self, name: str) -> str:
        self._dm.add_category(name)
        return json.dumps({'ok': True, 'categories': self._dm.get_categories()},
                          ensure_ascii=False)

    def deleteCategory(self, name: str) -> str:
        self._dm.delete_category(name)
        return json.dumps({'ok': True, 'categories': self._dm.get_categories()},
                          ensure_ascii=False)

    # ─── 文件系统操作 ─────────────────────────────────────────────────────────

    def openFileDialog(self, mode: str) -> str:
        """
        mode: 'file' | 'folder' | 'image'
        返回选择的路径, 取消返回空字符串
        """
        result = []

        def _run():
            try:
                # WinForms 对话框要求 STA 线程
                ctypes.windll.ole32.CoInitializeEx(None, 2)
                result.append(self._show_dialog(mode) or '')
            except Exception:
                result.append('')
            finally:
                ctypes.windll.ole32.CoUninitialize()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join()
        return result[0] if result else ''

    def _show_dialog(self, mode: str) -> str:
        import clr
        clr.AddReference('System.Windows.Forms')
        import System.Windows.Forms as WinForms

        start_dir = self._last_dialog_dir or ''
        if mode == 'folder':
            dlg = WinForms.FolderBrowserDialog()
            dlg.Description = '选择文件夹'
            if start_dir:
                dlg.SelectedPath = start_dir
            if dlg.ShowDialog() == WinForms.DialogResult.OK:
                path = dlg.SelectedPath
            else:
                return ''
        else:
            dlg = WinForms.OpenFileDialog()
            if mode == 'image':
                dlg.Filter = '图片文件|*.png;*.jpg;*.jpeg;*.bmp;*.ico;*.webp'
            else:
                dlg.Filter = '所有文件|*.*'
            if start_dir:
                dlg.InitialDirectory = start_dir
            if dlg.ShowDialog() == WinForms.DialogResult.OK:
                path = dlg.FileName
            else:
                return ''

        # 记住本次打开的目录, 下次直接定位到该层
        p = Path(path)
        self._last_dialog_dir = str(p.parent if not p.is_dir() else p)
        return path

    def detectFileType(self, path: str) -> str:
        return detect_type(path)

    def openFileLocation(self, tool_id: str) -> str:
        tool = self._dm.get_tool(tool_id)
        if not tool:
            return json.dumps({'ok': False, 'error': '工具不存在'}, ensure_ascii=False)
        ok, err = open_file_location(tool.get('path', ''))
        return json.dumps({'ok': ok, 'error': err}, ensure_ascii=False)

    def copyPath(self, tool_id: str) -> str:
        tool = self._dm.get_tool(tool_id)
        if not tool:
            return json.dumps({'ok': False, 'error': '工具不存在'}, ensure_ascii=False)
        self._set_clipboard_text(tool.get('path', ''))
        return json.dumps({'ok': True}, ensure_ascii=False)

    @staticmethod
    def _set_clipboard_text(text: str):
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        kernel32 = ctypes.windll.kernel32
        if not user32.OpenClipboard(None):
            return
        try:
            user32.EmptyClipboard()
            data = text.encode('utf-16-le') + b'\x00\x00'
            h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            ptr = kernel32.GlobalLock(h)
            ctypes.memmove(ptr, data, len(data))
            kernel32.GlobalUnlock(h)
            user32.SetClipboardData(CF_UNICODETEXT, h)
        finally:
            user32.CloseClipboard()

    def getFileInfo(self, path: str) -> str:
        """获取文件基本信息用于预填对话框 (.lnk 自动解析为目标文件路径)"""
        from .icon_extractor import resolve_lnk_target

        resolved = path
        if path and not path.startswith(('http://', 'https://')):
            p = Path(path)
            if p.suffix.lower() == '.lnk':
                target = resolve_lnk_target(path)
                if target and os.path.exists(target):
                    resolved = target

        info = {
            'name': Path(resolved).stem if resolved else '',
            'path': resolved,
            'type': detect_type(resolved),
        }
        return json.dumps(info, ensure_ascii=False)

    # ─── 窗口控制 ─────────────────────────────────────────────────────────────

    def minimizeWindow(self):
        try:
            self._window.minimize()
        except Exception:
            pass

    def closeWindow(self):
        try:
            self._window.destroy()
        except Exception:
            pass

    def setAlwaysOnTop(self, on_top: bool):
        try:
            self._window.on_top = bool(on_top)
        except Exception:
            pass

    # ─── OS 文件拖入 ──────────────────────────────────────────────────────────

    def on_files_dropped(self, event):
        """pywebview DOM API drop 事件回调 (已由框架配对完整路径)"""
        try:
            files = (event or {}).get('dataTransfer', {}).get('files', [])
            paths = [f.get('pywebviewFullPath') for f in files if f.get('pywebviewFullPath')]
        except Exception:
            return
        if paths:
            self._push('filesDropped', json.dumps(paths, ensure_ascii=False))

    # ─── 内部: 主动推送 (Python -> JS) ────────────────────────────────────────

    def _push(self, event: str, *args):
        win = self._window
        if win is None:
            return
        payload = ','.join(json.dumps(a, ensure_ascii=True) for a in args)
        script = f'window.AppBridge && window.AppBridge._emit("{event}"{"," + payload if payload else ""})'
        try:
            win.evaluate_js(script)
        except Exception:
            pass

    def _push_tools_updated(self):
        self._push('toolsUpdated',
                   json.dumps(self._dm.get_tools(), ensure_ascii=False))
