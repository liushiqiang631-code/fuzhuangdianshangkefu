@echo off
cd /d "%~dp0"
set TQDM_DISABLE=1
set PYTHONIOENCODING=utf-8
set APP_DEBUG=false
set PYTHON_EXE=C:\Users\LENOVO\AppData\Local\Programs\Python\Python313\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=python

echo ========================================
echo   Clothing E-Commerce Customer Service
echo ========================================
echo.

echo [1/3] Checking Python...
"%PYTHON_EXE%" --version
if errorlevel 1 (
    echo [ERROR] Python not found!
    pause
    exit /b 1
)

echo [2/3] Checking data...
if not exist "data\docs\products.json" (
    echo Generating sample data...
    "%PYTHON_EXE%" ingest.py --sample
) else (
    echo Data exists, skipping.
)

echo [3/3] Starting server...
echo.
echo   API docs: http://localhost:8000/docs
echo   Health:   http://localhost:8000/health
echo   Frontend: http://localhost:8000/ui
echo.

:: 等待 2 秒后自动打开浏览器
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

"%PYTHON_EXE%" -m app.main

pause
