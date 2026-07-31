@echo off
chcp 65001 >nul
title AI Second Brain

echo ========================================
echo   AI Second Brain — 一键启动
echo ========================================
echo.

cd /d H:\agent

:: 激活虚拟环境
call .venv\Scripts\activate.bat
set PYTHONUTF8=1

:: 启动桌面端（自动处理后端启停）
.venv\Scripts\python.exe desktop\main.py

echo.
echo ========================================
echo   Goodbye!
echo ========================================
pause
