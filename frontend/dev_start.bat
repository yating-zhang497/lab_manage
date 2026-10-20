@echo off
cd /d %~dp0
npm run dev > %TEMP%\vite_dev.log 2>&1
