@echo off
:: android-harness launcher — uses the project's clean venv
chcp 65001 > nul 2>&1
setlocal
set "AH_HOME=%~dp0"
set "AH_PYTHON=%AH_HOME%.venv\Scripts\python.exe"
set "PYTHONIOENCODING=utf-8"

if not exist "%AH_PYTHON%" (
    echo android-harness venv not found. Run: uv venv .venv ^&^& uv pip install -e . "paddlepaddle<3.0" "paddleocr<3.0" setuptools
    exit /b 1
)

"%AH_PYTHON%" -I -c "import sys; sys.path.insert(0, r'%AH_HOME%.venv\Lib\site-packages'); sys.path.insert(0, r'%AH_HOME%src'); from android_harness.run import main; main()" %*
