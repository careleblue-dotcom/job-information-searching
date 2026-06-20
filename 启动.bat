@echo off
chcp 65001 >nul
title 南京大学马克思主义学院就业信息网
cd /d "%~dp0"

echo ========================================
echo  南京大学马克思主义学院就业信息网
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python
    pause
    exit /b 1
)

:: 启动 HTTP 服务器
echo [1/2] 启动 HTTP 服务器 (http://localhost:8080)...
start "就业信息网服务器" /min python -m http.server 8080 --bind 127.0.0.1

:: 等待服务器就绪
ping 127.0.0.1 -n 2 >nul

:: 打开浏览器
echo [2/2] 正在打开浏览器...
start http://localhost:8080/index.html

echo.
echo 服务已启动！
echo 浏览器已自动打开 http://localhost:8080/index.html
echo.
echo 使用完毕后，请按任意键关闭服务器...
echo （或直接关闭此窗口）
echo.
pause

:: 停止服务器
echo 正在关闭服务器...
taskkill /f /fi "WINDOWTITLE eq 就业信息网服务器" >nul 2>&1
echo 已关闭。
