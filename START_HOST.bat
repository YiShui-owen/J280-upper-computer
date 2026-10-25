@echo off
chcp 65001 >nul
set "ROOT=%~dp0"
set "HOST_PYTHON=%ROOT%host\fd2\upstream\runtime\python.exe"
if not exist "%HOST_PYTHON%" (
  echo Missing bundled FD2 Python 3.12 runtime.
  pause
  exit /b 1
)
echo Select the firmware already programmed on J280.
echo 1. V1  Three swing-up profiles
echo 2. V2  SWM4 and optical gestures
echo 3. V3  Manual balance and adaptive angle P/D
echo 4. V4  Three swing-up profiles and six positions
echo 5. V5  Manual balance, six positions and six trajectories
echo Close the previous Host before using port 8371.
choice /c 12345 /n /m "Select V1-V5: "
set "HOST_VARIANT=V%ERRORLEVEL%"
pushd "%ROOT%"
"%HOST_PYTHON%" -B -X utf8 "%ROOT%launch_host.py" "%HOST_VARIANT%"
set "HOST_EXIT=%ERRORLEVEL%"
popd
if not "%HOST_EXIT%"=="0" pause
exit /b %HOST_EXIT%
