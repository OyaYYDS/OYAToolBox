@echo off
setlocal
cd /d "%~dp0"

rem 使用 python -m PyInstaller 确保调用当前环境 (已安装 pywebview) 的 PyInstaller,
rem 避免 PATH 中其它 Python 版本的 pyinstaller 被误用
echo [1/2] Clean old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [2/2] Building exe with PyInstaller...
python -m PyInstaller --noconfirm --clean OYAToolBox.spec

echo.
echo Build done. Output: dist\OYAToolBox\OYAToolBox.exe
pause
