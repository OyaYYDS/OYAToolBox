# OYAToolBox

Windows 桌面工具箱启动器（pywebview + WebView2）。

架构：HTML/CSS/JS 前端 + Python 后端（js_api 桥接），窗口由 WebView2（Edge Chromium）渲染，硬件加速、系统原生拖动/缩放。

## 当前版本功能

- 网格视图 / 列表视图
- 网格图标大小切换（小/中/大）
- 列表左右拖拽调整宽度、详情面板可隐藏
- 添加/编辑/删除工具，拖拽排序
- 右键菜单、悬浮信息卡
- 打开所在位置、复制路径
- 搜索（防抖）、6 种排序、分类管理
- 深色 / 浅色 / 跟随系统主题、窗口置顶、位置尺寸记忆
- 图标自动提取（exe/lnk/文件夹/关联图标，磁盘缓存）、自定义图片、文字图标
- Windows 11 亚克力毛玻璃 + 圆角（Win10 自动回落）

## 环境要求

- Windows 10 (1903+) / Windows 11
- Python 3.10+
- WebView2 Runtime：Win11 预装；Win10 安装包会自动安装（见下文），或手动下载 [Evergreen 引导程序](https://developer.microsoft.com/microsoft-edge/webview2/)

## 安装依赖

```bash
pip install -r requirements.txt
```

（`pywebview` 在 Windows 上会自动安装 `pythonnet`，即 .NET 桥接，Win10/11 系统内置 .NET Framework 4.8。）

## 本地运行

```bash
python main.py
```

调试模式（显示 WebView2 控制台）：设置环境变量 `OYA_DEBUG=1`。

## 打包

直接运行：

```bat
build_exe.bat
```

输出：

- `dist/OYAToolBox/OYAToolBox.exe`（onedir，约 40–60 MB）
- `dist/OYAToolBox/_internal`（运行所需依赖目录，不要删除）

## 制作安装包（Inno Setup 6）

1. 安装 [Inno Setup 6](https://jrsoftware.org/isdl.php)（无管理员权限可用 `/PORTABLE=1` 便携安装）
2. 下载 [WebView2 Evergreen 引导程序](https://developer.microsoft.com/microsoft-edge/webview2/)，重命名为 `MicrosoftEdgeWebview2Setup.exe` 放到项目根目录（仓库内已附带）
3. 编译：`ISCC.exe OYAToolBox.iss`，输出 `dist\OYAToolBox-Setup.exe`（约 16 MB）

安装行为：

- 默认安装到 Program Files（安装时自动检测并按需安装 WebView2 Runtime）
- **初始数据适配**：安装包会携带当前 `data/` 作为初始数据；安装到 Program Files 后程序首启自动把初始数据播种到 `%APPDATA%\OYAToolBox`（只读源文件、已有数据不覆盖）
- 便携模式：把 `dist\OYAToolBox` 整个目录拷到任意可写位置运行即可，数据保存在 exe 同目录 `data/`

## 数据存储

| 内容 | 位置 |
|---|---|
| 工具列表 / 设置 | 便携模式：exe 同目录 `data/`；不可写时：`%APPDATA%\OYAToolBox\` |
| 图标缓存 | `%LOCALAPPDATA%\OYAToolBox\icons\` |

## 主要目录

- [app](app)：Python 后端（js_api、数据管理、图标提取、窗口特效、工具启动）
- [web](web)：前端页面与交互
- [docs](docs)：项目分析与重构方案文档
- [data](data)：开发模式下的工具与设置数据（打包后自动生成到用户目录）

## 备注

- 图标文件使用 [OYAToolBoxICO.ico](OYAToolBoxICO.ico)
- 仅供个人学习与使用
