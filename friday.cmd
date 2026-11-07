@echo off
title Friday AI - Terminal Mode
cd /d "%~dp0"
.\.venv\Scripts\python.exe main.py %*
