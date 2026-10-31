@echo off
title VastraView - Connect Colab GPU
cd /d "%~dp0"
echo ============================================================
echo           VastraView - Connect Colab GPU Worker
echo ============================================================
echo.
echo Paste your Colab connection JSON or Gradio URL and press Enter:
echo.
.venv\Scripts\python.exe scripts\connect_colab.py
echo.
pause
