# 工具箱启动器

一个基于 PySide6 + QWebEngine 的 Windows 桌面工具箱启动器，支持工具管理、分类筛选、双视图显示与基础主题切换。

---

## 功能特性

- 双视图模式：网格视图 / 卡片视图
- 工具管理：添加、编辑、删除、拖拽排序
- 支持类型：exe、bat、cmd、ps1、lnk、folder、url、file
- 图标来源：自动提取 exe 图标 / 自定义图片 / 文字图标
- 分类管理：自定义分类、快速筛选
- 右键菜单：启动、编辑、删除、打开所在位置、复制路径
- 外观设置：深色、浅色、跟随系统
- 窗口功能：始终置顶、窗口位置与尺寸记忆
- 统一应用图标：使用项目根目录 OYAToolBoxICO.ico（任务栏、窗口、标题栏）

---

## 技术栈

| 组件 | 版本要求 |
|---|---|
| Python | 3.10+ |
| PySide6 | >= 6.6.0 |
| qasync | >= 0.27.0 |
| Pillow | >= 10.0.0 |
| pywin32 | >= 306 |
| pywin32-ctypes | >= 0.2.2 |

前端为原生 HTML/CSS/JavaScript，通过 QWebChannel 与 Python 后端通信。

---

## 项目结构

```text
工具箱启动器2/
├── main.py               # 启动入口（含 Conda PATH 兼容与 WebEngine 启动参数）
├── requirements.txt      # 依赖列表
├── install.bat           # 安装依赖脚本
├── build_exe.bat         # PyInstaller 打包脚本
├── OYAToolBox.spec       # PyInstaller 规格文件
├── OYAToolBox.iss        # Inno Setup 安装包脚本
├── OYAToolBoxICO.ico     # 应用图标
├── app/
│   ├── bridge.py
│   ├── data_manager.py
│   ├── icon_extractor.py
│   ├── tool_launcher.py
│   └── window.py
├── web/
│   ├── index.html
│   ├── css/
│   └── js/
├── data/
│   ├── tools.json
│   └── settings.json
└── .gitignore
```

---

## 开发运行

### 方式一：脚本安装

双击执行 install.bat，之后运行：

```bash
python main.py
```

### 方式二：手动安装

```bash
pip install -r requirements.txt
python main.py
```

Conda 用户说明：main.py 已包含 PATH 清理逻辑，用于规避 Conda Library/bin 与 PySide6 的 DLL 冲突。

---

## 打包发布

### 1) 生成可执行目录（PyInstaller）

推荐直接执行：

```bat
build_exe.bat
```

产物目录：dist/OYAToolBox/

### 2) 生成安装包（Inno Setup 6）

- 打开 OYAToolBox.iss
- 在 Inno Setup 6 中编译
- 输出安装包位于 dist/ 目录

---

## 数据文件

- data/tools.json：工具数据（名称、路径、类型、图标、分类、排序等）
- data/settings.json：用户偏好（主题、视图、排序、置顶、窗口位置尺寸、分类等）

程序会自动维护这两个文件，通常不需要手动编辑。

---

## 常见问题

### Q1：启动时报 DLL 错误或白屏

- 优先确认 Python 版本为 3.10+
- 通过 main.py 启动以应用 PATH 修复逻辑
- 使用 build_exe.bat 重新打包，避免参数不一致

### Q2：为什么打包后有 _internal 文件夹

这是 PyInstaller onedir 模式的正常结构，依赖与运行资源都在该目录中，不建议手动删除。

### Q3：为什么设置里没有背景透明度/模糊/背景图片

这些功能已在当前版本移除，外观设置仅保留主题相关选项。

---

## License

仅供个人学习与使用。
