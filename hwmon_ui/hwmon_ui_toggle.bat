@echo off
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0hwmon_ui_toggle.ps1" %*

