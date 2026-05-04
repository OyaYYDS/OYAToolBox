@echo off
chcp 65001 > nul
echo ============================================
echo   工具箱启动器 - 安装并启动
echo ============================================
echo.
echo [1/2] 正在安装 Python 依赖...
pip install -r requirements.txt
if errorlevel 1 (
    echo 依赖安装失败，请检查 Python 和 pip 环境
    pause
    exit /b 1
)
echo.
echo [2/2] 启动工具箱启动器...
python main.py
if errorlevel 1 (
    echo 启动失败，请检查错误信息
    pause
)
