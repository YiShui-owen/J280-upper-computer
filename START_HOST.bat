@echo off
chcp 65001 >nul
set "ROOT=%~dp0"
set "HOST_PYTHON=python"
if exist "%ROOT%.venv\Scripts\python.exe" set "HOST_PYTHON=%ROOT%.venv\Scripts\python.exe"
echo Select the Host matching the firmware programmed on J280.
echo 1. SG21 Gesture
echo 2. SA21 Adaptive
echo 3. SP24 Precise telemetry / gesture / adaptive
echo Close an existing Host before starting another on port 8371.
choice /c 123 /n /m "Select 1, 2 or 3: "
if errorlevel 3 (
  set "HOST_VARIANT=precise"
) else if errorlevel 2 (
  set "HOST_VARIANT=adaptive"
) else (
  set "HOST_VARIANT=gesture"
)
pushd "%ROOT%"
"%HOST_PYTHON%" -B -X utf8 "%ROOT%launch_host.py" "%HOST_VARIANT%"
set "HOST_EXIT=%ERRORLEVEL%"
popd
if not "%HOST_EXIT%"=="0" pause
exit /b %HOST_EXIT%
