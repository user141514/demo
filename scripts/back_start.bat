@echo off
pwsh -NoProfile -File "%~dp0start_local.ps1" -BackendOnly %*
exit /b %errorlevel%
