# 工具箱启动器

一个基于 **PySide6 + QWebEngine** 的 Windows 桌面工具箱启动器，拥有磨砂玻璃风格 UI，支持多种工具类型管理、自定义背景与主题切换。

---

## 功能特性

- **双视图模式**：网格视图（紧凑图标）/ 卡片视图（详细列表）
- **工具管理**：添加、编辑、删除工具；支持拖拽排序
- **多种工具类型**：
  - 可执行程序（`.exe`）
  - 脚本（`.cmd` / `.ps1` / `.py`）
  - 文件夹（直接打开）
  - 网页链接（URL）
- **图标来源**：
  - 自动从 `.exe` 提取图标
  - 自定义图片（PNG / JPG 等）
  - 文字 / Emoji + 自定义背景色
- **分类管理**：自定义分类标签，快速筛选工具
- **悬浮卡片**：鼠标悬停工具时展示名称、类型、路径等详情
- **右键菜单**：快速启动、打开文件位置、编辑、删除
- **外观设置**：
  - 主题模式：深色 / 浅色 / 跟随系统
  - 背景透明度：0–100% 无级调节
  - 背景模糊强度：0–40px 高斯模糊
  - 自定义背景图片
  - 窗口始终置顶
- **窗口记忆**：自动保存位置、大小，下次启动恢复

---

## 技术栈

| 组件 | 版本要求 |
|---|---|
| Python | 3.10+ |
| PySide6 | ≥ 6.6.0 |
| qasync | ≥ 0.27.0 |
| Pillow | ≥ 10.0.0 |
| pywin32 | ≥ 306 |
| pywin32-ctypes | ≥ 0.2.2 |

前端使用纯 HTML/CSS/JavaScript，通过 **QWebChannel** 实现 Python ↔ JavaScript 双向通信。

---

## 项目结构

```
工具箱启动器2/
├── main.py                  # 入口，启动 Qt 事件循环（含 Conda PATH 修复）
├── requirements.txt         # Python 依赖列表
├── install.bat              # 一键安装依赖脚本
├── 图标.ico                  # 应用图标
├── app/
│   ├── bridge.py            # QWebChannel 桥接层（Python ↔ JS）
│   ├── data_manager.py      # 工具数据 & 设置的读写管理
│   ├── icon_extractor.py    # 从 exe 提取图标并转为 Base64
│   ├── tool_launcher.py     # 启动工具、打开文件位置
│   └── window.py            # 主窗口（QMainWindow + QWebEngineView）
├── web/
│   ├── index.html           # 主页面
│   ├── css/
│   │   ├── themes.css       # 深色 / 浅色主题 CSS 变量
│   │   └── main.css         # 全局组件样式
│   └── js/
│       ├── app.js           # 应用主控制器
│       ├── settings_panel.js # 设置面板逻辑
│       ├── grid_view.js     # 网格视图渲染
│       ├── card_view.js     # 卡片视图渲染
│       ├── hover_card.js    # 悬浮卡片组件
│       ├── add_dialog.js    # 添加 / 编辑工具弹窗
│       ├── context_menu.js  # 右键菜单
│       └── drag_handler.js  # 窗口拖拽 & 工具排序
└── data/
    ├── tools.json           # 工具列表持久化数据
    └── settings.json        # 用户设置持久化数据
```

---

## 安装与运行

### 方式一：一键安装（推荐）

双击运行 `install.bat`，自动安装所有依赖，然后运行：

```bash
python main.py
```

### 方式二：手动安装

```bash
pip install -r requirements.txt
python main.py
```

> **Conda 用户注意**：`main.py` 已内置 PATH 清理逻辑，会自动过滤 Conda `Library\bin` 中与 PySide6 冲突的 DLL，无需手动处理。

---

## 数据文件说明

- **`data/tools.json`**：存储所有工具的配置（名称、路径、类型、图标、分类、排序等）
- **`data/settings.json`**：存储用户偏好（主题、背景图、透明度、模糊强度、窗口位置等）

这两个文件由程序自动维护，一般无需手动编辑。

---

## 常见问题

**Q：程序启动时崩溃或报 DLL 错误？**  
A：通常是 Conda 环境中 `Library\bin` 的 OpenSSL / Qt DLL 与 PySide6 冲突。本项目已在 `main.py` 中自动处理，如仍有问题，请确认使用的是 Python 3.10 及以上版本。

**Q：图标无法显示？**  
A：确认 `pywin32` 已正确安装。对于非标准路径或 UNC 路径，图标提取可能不支持，程序会自动回退到默认图标。

**Q：背景图片不显示？**  
A：请确认图片路径中不含特殊符号，建议使用绝对路径，路径可通过设置面板的"浏览"按钮选择。

---

## License

仅供个人学习与使用。
