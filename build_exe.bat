@echo off
chcp 65001 >nul
echo 正在打包 NCM 音乐格式转换器为单文件 EXE...
pyinstaller --noconfirm --onefile --windowed --add-binary "ncm main.exe;." --name "NCM音乐格式转换器" app.py
if %errorlevel% equ 0 (
    echo 打包成功！文件保存在 dist\NCM音乐格式转换器.exe
) else (
    echo 打包失败，请检查是否已安装 pyinstaller。
)
pause
