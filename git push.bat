@echo off
cd /d "D:\TTS\styletts2-ukrainian"
echo === Adding changes ===
git add -A

echo === Commit ===
set /p msg=Enter commit message: 
if "%msg%"=="" set msg=update
git commit -m "%msg%"

echo === Push to GitHub ===
git push -u origin main

echo === Done ===
pause
