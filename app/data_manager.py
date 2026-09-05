"""数据管理器 - 负责工具列表和设置的持久化存储"""
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_SETTINGS: Dict[str, Any] = {
    'theme': 'dark',
    'always_on_top': False,
    'view_mode': 'grid',
    'grid_icon_size': 'medium',
    'card_detail_hidden': False,
    'card_list_ratio': 0.49,   # 列表视图左侧列表宽度占窗口宽度的比例 (随窗口缩放)
    'sort_by': 'manual',
    'window_x': -1,
    'window_y': -1,
    'window_width': 800,
    'window_height': 600,
    'categories': ['全部', '常用', '开发', '系统', '网络', '办公'],
}


def _resolve_data_dir() -> Path:
    """数据目录解析:
    - 源码运行: 仓库 data/
    - 打包运行: 优先 exe 同目录 data/ (便携), 不可写时回退 %APPDATA%\\OYAToolBox
    """
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent
        candidate = exe_dir / 'data'
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / '.write_test'
            probe.touch()
            probe.unlink()
            return candidate
        except OSError:
            appdata = Path(os.environ.get('APPDATA') or str(Path.home()))
            fallback = appdata / 'OYAToolBox'
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback
    return Path(__file__).resolve().parent.parent / 'data'


DATA_DIR = _resolve_data_dir()


class DataManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.tools_file = DATA_DIR / 'tools.json'
        self.settings_file = DATA_DIR / 'settings.json'
        self._tools: List[Dict] = []
        self._settings: Dict = {}
        self._seed_from_bundled()
        self._load()

    def _seed_from_bundled(self):
        """安装版首启: 从安装目录 data/ 导入随包发布的数据

        安装到 Program Files 时 exe 目录不可写, 实际数据在 %APPDATA%,
        这里只读取安装目录的初始数据播种过去 (不修改原文件, 已有数据时不覆盖)。
        """
        if not getattr(sys, 'frozen', False):
            return
        try:
            exe_dir = Path(sys.executable).resolve().parent
            bundled = exe_dir / 'data'
            if not bundled.is_dir() or bundled == DATA_DIR:
                return
            for name in ('tools.json', 'settings.json'):
                src = bundled / name
                dst = DATA_DIR / name
                if src.exists() and not dst.exists():
                    dst.write_text(src.read_text(encoding='utf-8'), encoding='utf-8')
        except Exception:
            pass

    def _load(self):
        if self.tools_file.exists():
            try:
                with open(self.tools_file, 'r', encoding='utf-8') as f:
                    self._tools = json.load(f)
            except Exception:
                self._tools = []
        else:
            self._tools = []
            self._save_tools()

        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._settings = {**DEFAULT_SETTINGS, **data}
            except Exception:
                self._settings = DEFAULT_SETTINGS.copy()
        else:
            self._settings = DEFAULT_SETTINGS.copy()
            self._save_settings()

    # ─── Tools ────────────────────────────────────────────────────────────────

    def get_tools(self) -> List[Dict]:
        return list(self._tools)

    def get_tool(self, tool_id: str) -> Optional[Dict]:
        for t in self._tools:
            if t.get('id') == tool_id:
                return t
        return None

    def add_tool(self, tool: Dict) -> Dict:
        if 'id' not in tool or not tool['id']:
            tool['id'] = str(uuid.uuid4())
        if 'created_at' not in tool:
            tool['created_at'] = time.time()
        tool.setdefault('last_used', None)
        tool.setdefault('use_count', 0)
        tool.setdefault('order', len(self._tools))
        tool.setdefault('icon_mode', 'auto')
        tool.setdefault('icon_data', '')
        tool.setdefault('icon_source', '')   # 程序/DLL 图标模式的来源文件
        tool.setdefault('icon_index', 0)     # 程序/DLL 图标模式的图标索引
        tool.setdefault('icon_text', self._name_to_abbr(tool.get('name', '?')))
        tool.setdefault('icon_color', self._name_to_color(tool.get('name', '')))
        tool.setdefault('category', '常用')
        tool.setdefault('tags', [])
        tool.setdefault('args', '')
        tool.setdefault('work_dir', '')
        tool.setdefault('description', '')
        self._tools.append(tool)
        self._save_tools()
        return tool

    def update_tool(self, tool_id: str, updates: Dict) -> Optional[Dict]:
        for i, t in enumerate(self._tools):
            if t.get('id') == tool_id:
                self._tools[i] = {**t, **updates}
                self._save_tools()
                return self._tools[i]
        return None

    def delete_tool(self, tool_id: str) -> bool:
        for i, t in enumerate(self._tools):
            if t.get('id') == tool_id:
                self._tools.pop(i)
                self._save_tools()
                return True
        return False

    def reorder_tools(self, ids: List[str]) -> None:
        tools_map = {t['id']: t for t in self._tools}
        ordered = []
        for i, tool_id in enumerate(ids):
            if tool_id in tools_map:
                tools_map[tool_id]['order'] = i
                ordered.append(tools_map[tool_id])
        for t in self._tools:
            if t.get('id') not in ids:
                ordered.append(t)
        self._tools = ordered
        self._save_tools()

    def record_usage(self, tool_id: str) -> None:
        for t in self._tools:
            if t.get('id') == tool_id:
                t['last_used'] = time.time()
                t['use_count'] = t.get('use_count', 0) + 1
                break
        self._save_tools()

    # ─── Settings ─────────────────────────────────────────────────────────────

    def get_settings(self) -> Dict:
        return dict(self._settings)

    def save_settings(self, settings: Dict) -> None:
        self._settings = {**DEFAULT_SETTINGS, **settings}
        self._save_settings()

    def update_setting(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self._save_settings()

    # ─── Categories ───────────────────────────────────────────────────────────

    def get_categories(self) -> List[str]:
        return list(self._settings.get('categories', DEFAULT_SETTINGS['categories']))

    def add_category(self, name: str) -> None:
        cats = self.get_categories()
        if name not in cats:
            cats.append(name)
            self._settings['categories'] = cats
            self._save_settings()

    def delete_category(self, name: str) -> None:
        cats = self.get_categories()
        if name in cats and name != '全部':
            cats.remove(name)
            self._settings['categories'] = cats
            self._save_settings()

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _save_tools(self):
        self._write_json(self.tools_file, self._tools)

    def _save_settings(self):
        self._write_json(self.settings_file, self._settings)

    @staticmethod
    def _write_json(path: Path, data: Any):
        """原子写入: 先写临时文件再替换, 避免写入中断损坏数据"""
        tmp = path.with_suffix(path.suffix + '.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    @staticmethod
    def _name_to_abbr(name: str) -> str:
        if not name:
            return '?'
        words = name.strip().split()
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        if len(name) >= 2:
            return name[:2].upper()
        return name[0].upper()

    @staticmethod
    def _name_to_color(name: str) -> str:
        colors = [
            '#4a9eff', '#ff6b6b', '#51cf66', '#ffd43b', '#cc5de8',
            '#ff922b', '#20c997', '#74c0fc', '#f783ac', '#a9e34b',
        ]
        idx = sum(ord(c) for c in name) % len(colors) if name else 0
        return colors[idx]
