@echo off
REM Отримати абсолютний шлях до папки, де запущено цей скрипт
set "VENV_DIR=%~dp0venv"

REM Створити віртуальне середовище
python -m venv "%VENV_DIR%"

REM Активувати віртуальне середовище
call "%VENV_DIR%\Scripts\activate"

echo Віртуальне середовище створено у: %VENV_DIR%
echo Тепер можна встановлювати залежності, наприклад:
echo pip install torch torchvision
