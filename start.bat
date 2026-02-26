@echo off
cd /d "%~dp0"

echo ======================================================
echo    AI 视频流水线 MVP
echo ======================================================

:: 1. 检查 Python
echo [1/3] 正在检测系统 Python...
call python --version
if %errorlevel% neq 0 (
    echo [错误] 找不到 python 命令。
    pause
    exit /b
)

:: 2. 检查虚拟环境
echo [2/3] 正在检查虚拟环境 (venv)...
if not exist "venv\Scripts\python.exe" (
    echo [提示] 正在自动创建虚拟环境，请耐心等待...
    call python -m venv venv
)

:: 3. 清理被占用的端口 (预防上次未正常关闭)
echo [3/4] 正在检查和清理 8000 端口...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr "0.0.0.0:8000"') do (
    if "%%a" neq "0" (
        echo [提示] 发现端口被 PID: %%a 占用，正在强制释放...
        taskkill /F /PID %%a >nul 2>&1
    )
)

:: 4. 运行程序
echo [4/4] 正在启动服务...
echo 马上为您自动打开浏览器，请稍作等待...
echo.

:: 延迟两秒后自动在默认浏览器打开网页
start cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"

cmd /k ".\venv\Scripts\python.exe web\app.py"

