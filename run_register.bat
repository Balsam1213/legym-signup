@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
py register.py 1>>logs\run.out 2>&1
