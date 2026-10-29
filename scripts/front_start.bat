@echo off
pwsh -NoProfile -File "%~dp0start_local.ps1" -FrontendOnly %*
exit /b %errorlevel%
