"""QWebChannel 桥接 - Python 与 JavaScript 通信"""
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Slot, Signal, QTimer
from PySide6.QtWidgets import QFileDialog, QApplication
from PySide6.QtGui import QClipboard

from .data_manager import DataManager
from .icon_extractor import extract_icon, generate_text_icon
from .tool_launcher import launch_tool, open_file_location, detect_type


class Bridge(QObject):
    # ─── Python -> JS 信号 ───────────────────────────────────────────────────
    toolsUpdated = Signal(str)        # JSON 工具列表
    settingsUpdated = Signal(str)     # JSON 设置
    iconLoaded = Signal(str, str)     # tool_id, base64_icon
    errorOccurred = Signal(str)       # 错误消息
    filesDropped = Signal(str)        # JSON 路径列表 (OS 拖拽)
    windowMoveRequest = Signal(int, int)
    windowResizeRequest = Signal(int, int)
    windowMinimizeRequest = Signal()
    windowCloseRequest = Signal()
    windowAlwaysOnTopRequest = Signal(bool)

    def __init__(self, parent: QObject, data_manager: DataManager):
        super().__init__(parent)
        self._dm = data_manager
        self._icon_queue: list = []
        self._icon_lock = threading.Lock()
        self._last_dialog_dir: str = ''

        # 定时器从主线程分发异步图标结果
        self._icon_timer = QTimer(self)
        self._icon_timer.setInterval(50)
        self._icon_timer.timeout.connect(self._flush_icon_queue)
        self._icon_timer.start()

    # ─── 工具 CRUD ────────────────────────────────────────────────────────────

    @Slot(result=str)
    def getTools(self) -> str:
        return json.dumps(self._dm.get_tools(), ensure_ascii=False)

    @Slot(str, result=str)
    def addTool(self, tool_json: str) -> str:
        try:
            tool = json.loads(tool_json)
            saved = self._dm.add_tool(tool)
            self.toolsUpdated.emit(json.dumps(self._dm.get_tools(), ensure_ascii=False))
            return json.dumps({'ok': True, 'tool': saved}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)

    @Slot(str, str, result=str)
    def updateTool(self, tool_id: str, updates_json: str) -> str:
        try:
            updates = json.loads(updates_json)
            result = self._dm.update_tool(tool_id, updates)
            if result:
                self.toolsUpdated.emit(json.dumps(self._dm.get_tools(), ensure_ascii=False))
                return json.dumps({'ok': True, 'tool': result}, ensure_ascii=False)
            return json.dumps({'ok': False, 'error': '工具不存在'}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)

    @Slot(str, result=str)
    def deleteTool(self, tool_id: str) -> str:
        ok = self._dm.delete_tool(tool_id)
        if ok:
            self.toolsUpdated.emit(json.dumps(self._dm.get_tools(), ensure_ascii=False))
        return json.dumps({'ok': ok}, ensure_ascii=False)

    @Slot(str, result=str)
    def reorderTools(self, ids_json: str) -> str:
        try:
            ids = json.loads(ids_json)
            self._dm.reorder_tools(ids)
            return json.dumps({'ok': True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)

    @Slot(str, result=str)
    def launchTool(self, tool_id: str) -> str:
        tool = self._dm.get_tool(tool_id)
        if not tool:
            return json.dumps({'ok': False, 'error': '工具不存在'}, ensure_ascii=False)
        ok, err = launch_tool(tool)
        if ok:
            self._dm.record_usage(tool_id)
        return json.dumps({'ok': ok, 'error': err}, ensure_ascii=False)

    # ─── 图标 ─────────────────────────────────────────────────────────────────

    @Slot(str, str)
    def requestIcon(self, tool_id: str, path: str):
        """异步提取图标，完成后通过 iconLoaded 信号返回"""
        threading.Thread(
            target=self._icon_worker,
            args=(tool_id, path),
            daemon=True
        ).start()

    def _icon_worker(self, tool_id: str, path: str):
        icon = extract_icon(path)
        if not icon:
            tool = self._dm.get_tool(tool_id)
            name = tool.get('name', '?') if tool else '?'
            color = tool.get('icon_color', '#4a9eff') if tool else '#4a9eff'
            icon = generate_text_icon(name, color) or ''
        with self._icon_lock:
            self._icon_queue.append((tool_id, icon))

    def _flush_icon_queue(self):
        with self._icon_lock:
            items = list(self._icon_queue)
            self._icon_queue.clear()
        for tool_id, icon in items:
            self.iconLoaded.emit(tool_id, icon)

    @Slot(str, result=str)
    def extractIconSync(self, path: str) -> str:
        """同步提取图标（用于对话框预览，路径较短可接受）"""
        icon = extract_icon(path)
        return icon or ''

    # ─── 设置 ─────────────────────────────────────────────────────────────────

    @Slot(result=str)
    def getSettings(self) -> str:
        return json.dumps(self._dm.get_settings(), ensure_ascii=False)

    @Slot(str, result=str)
    def saveSettings(self, settings_json: str) -> str:
        try:
            settings = json.loads(settings_json)
            self._dm.save_settings(settings)
            self.settingsUpdated.emit(json.dumps(self._dm.get_settings(), ensure_ascii=False))
            return json.dumps({'ok': True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False)

    # ─── 分类 ─────────────────────────────────────────────────────────────────

    @Slot(result=str)
    def getCategories(self) -> str:
        return json.dumps(self._dm.get_categories(), ensure_ascii=False)

    @Slot(str, result=str)
    def addCategory(self, name: str) -> str:
        self._dm.add_category(name)
        return json.dumps({'ok': True, 'categories': self._dm.get_categories()},
                          ensure_ascii=False)

    @Slot(str, result=str)
    def deleteCategory(self, name: str) -> str:
        self._dm.delete_category(name)
        return json.dumps({'ok': True, 'categories': self._dm.get_categories()},
                          ensure_ascii=False)

    # ─── 文件系统操作 ─────────────────────────────────────────────────────────

    @Slot(str, result=str)
    def openFileDialog(self, mode: str) -> str:
        """
        mode: 'file' | 'folder' | 'image'
        返回选择的路径，取消返回空字符串
        """
        start_dir = self._last_dialog_dir
        if mode == 'folder':
            path = QFileDialog.getExistingDirectory(
                None, '选择文件夹', start_dir,
                QFileDialog.Option.ShowDirsOnly
            )
        elif mode == 'image':
            path, _ = QFileDialog.getOpenFileName(
                None, '选择图片', start_dir,
                '图片文件 (*.png *.jpg *.jpeg *.bmp *.ico *.webp)'
            )
        else:
            path, _ = QFileDialog.getOpenFileName(
                None, '选择文件', start_dir,
                '所有文件 (*.*)'
            )
        if path:
            # 记住本次打开的目录，下次直接定位到该层
            import os as _os
            self._last_dialog_dir = _os.path.dirname(path) if not _os.path.isdir(path) else path
        return path or ''

    @Slot(str, result=str)
    def detectFileType(self, path: str) -> str:
        return detect_type(path)

    @Slot(str, result=str)
    def openFileLocation(self, tool_id: str) -> str:
        tool = self._dm.get_tool(tool_id)
        if not tool:
            return json.dumps({'ok': False, 'error': '工具不存在'}, ensure_ascii=False)
        ok, err = open_file_location(tool.get('path', ''))
        return json.dumps({'ok': ok, 'error': err}, ensure_ascii=False)

    @Slot(str, result=str)
    def copyPath(self, tool_id: str) -> str:
        tool = self._dm.get_tool(tool_id)
        if not tool:
            return json.dumps({'ok': False, 'error': '工具不存在'}, ensure_ascii=False)
        path = tool.get('path', '')
        QApplication.clipboard().setText(path)
        return json.dumps({'ok': True}, ensure_ascii=False)

    @Slot(str, result=str)
    def getFileInfo(self, path: str) -> str:
        """获取文件基本信息用于预填对话框"""
        info = {
            'name': Path(path).stem if path else '',
            'path': path,
            'type': detect_type(path),
        }
        return json.dumps(info, ensure_ascii=False)

    # ─── 窗口控制 ─────────────────────────────────────────────────────────────

    @Slot(int, int)
    def moveWindow(self, dx: int, dy: int):
        self.windowMoveRequest.emit(dx, dy)

    @Slot(int, int)
    def resizeWindow(self, width: int, height: int):
        self.windowResizeRequest.emit(width, height)

    @Slot()
    def minimizeWindow(self):
        self.windowMinimizeRequest.emit()

    @Slot()
    def closeWindow(self):
        self.windowCloseRequest.emit()

    @Slot(bool)
    def setAlwaysOnTop(self, on_top: bool):
        self.windowAlwaysOnTopRequest.emit(on_top)

    # ─── 被动通知（供 window.py 调用）────────────────────────────────────────

    def notify_files_dropped(self, paths: list):
        self.filesDropped.emit(json.dumps(paths, ensure_ascii=False))
