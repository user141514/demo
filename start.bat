@echo off
pwsh -NoProfile -File "%~dp0scripts\start_local.ps1" %*
exit /b %errorlevel%
