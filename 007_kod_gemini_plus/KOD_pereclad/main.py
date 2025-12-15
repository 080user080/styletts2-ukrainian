#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_controller_simple.py
Спрощений головний контролер з кольоровим логуванням та вимірюванням часу
"""

import os
import sys
import time
import logging
import subprocess
import pyperclip
from pathlib import Path

# Спробуємо імпортувати colorlog
try:
    import colorlog
    COLORLOG_AVAILABLE = True
except ImportError:
    COLORLOG_AVAILABLE = False
    print("ℹ️ Бібліотека colorlog не встановлена. Використовую стандартне логування.")
    print("   Для кольорового логування встановіть: pip install colorlog")

def setup_color_logging():
    """Налаштування кольорового логування для основного логера"""
    if COLORLOG_AVAILABLE:
        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'white',      # Білий для INFO
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            },
            secondary_log_colors={},
            style='%'
        ))
        
        logger = colorlog.getLogger("main_controller")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        return logging.getLogger("main_controller")

def setup_time_logger():
    """Налаштування окремого логера для часу виконання"""
    if COLORLOG_AVAILABLE:
        handler = colorlog.StreamHandler()
        handler.setFormatter(colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s [TIME] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'INFO': 'green',      # Зелений для TIME INFO
                'WARNING': 'yellow',
                'ERROR': 'red',
            }
        ))
        
        logger = colorlog.getLogger("time_logger")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger
    else:
        logger = logging.getLogger("time_logger")
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [TIME] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

# Налаштування логерів
logger = setup_color_logging()
time_logger = setup_time_logger()

def run_script_simple(script_name, args=None):
    """Запуск скрипта з вимірюванням часу виконання"""
    try:
        cmd = [sys.executable, script_name]
        if args:
            cmd.extend(args)
            
        logger.info(f"🚀 Запуск {script_name}...")
        start_time = time.time()
        
        result = subprocess.run(
            cmd, 
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120
        )
        
        execution_time = time.time() - start_time
        
        if result.returncode == 0:
            logger.info(f"✅ {script_name} успішно виконано")
            time_logger.info(f"✅ {script_name} Час виконання: {execution_time:.2f} сек")
            return True, execution_time
        elif script_name == "1_folder_loader.py" and result.returncode == 1:
            logger.info(f"ℹ️ {script_name} завершив з кодом 1 (можливо, папка вже налаштована)")
            time_logger.info(f"ℹ️ {script_name} Час виконання: {execution_time:.2f} сек")
            return True, execution_time
        else:
            logger.warning(f"⚠️ {script_name} завершився з кодом {result.returncode}")
            time_logger.warning(f"⚠️ {script_name} Час виконання: {execution_time:.2f} сек")
            return False, execution_time
            
    except subprocess.TimeoutExpired:
        execution_time = time.time() - start_time if 'start_time' in locals() else 0
        logger.error(f"⏰ Таймаут запуску {script_name}")
        time_logger.error(f"⏰ {script_name} Час виконання: {execution_time:.2f} сек (таймаут)")
        return False, execution_time
    except Exception as e:
        execution_time = time.time() - start_time if 'start_time' in locals() else 0
        logger.error(f"❌ Помилка запуску {script_name}: {e}")
        time_logger.error(f"❌ {script_name} Час виконання: {execution_time:.2f} сек")
        return False, execution_time

def get_response_from_clipboard():
    """Отримати відповідь з буфера обміну"""
    try:
        response_text = pyperclip.paste()
        if response_text and response_text.strip():
            logger.info(f"✅ Відповідь отримано з буфера обміну ({len(response_text)} символів)")
            return response_text.strip()
        else:
            logger.warning("⚠️ Буфер обміну порожній")
            return None
    except Exception as e:
        logger.error(f"❌ Помилка читання буфера обміну: {e}")
        return None

def get_input_folder():
    """Отримати папку введення з конфігурації"""
    try:
        import yaml
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        input_folder = config.get("input_folder", "input")
        
        if not os.path.exists(input_folder):
            logger.error(f"❌ Папка {input_folder} не існує")
            return None
            
        return input_folder
    except Exception as e:
        logger.error(f"❌ Помилка читання конфігу: {e}")
        return "input"

def print_colored_time(total_seconds):
    """Друкує загальний час виконання зеленим кольором"""
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    
    if COLORLOG_AVAILABLE:
        if minutes > 0:
            print(f"\033[92m[TIME]:------Час виконання: {minutes} хв {seconds} сек\033[0m")
        else:
            print(f"\033[92m[TIME]:------Час виконання: {seconds} сек\033[0m")
    else:
        if minutes > 0:
            print(f"[TIME]:------Час виконання: {minutes} хв {seconds} сек")
        else:
            print(f"[TIME]:------Час виконання: {seconds} сек")

def main():
    """Головна функція контролера"""
    total_start_time = time.time()
    logger.info("🎬 Запуск головного контролера перекладу")
    
    # Перевірка конфігурації
    if not os.path.exists("config.yaml"):
        logger.info("📝 Конфіг не знайдено, створюю...")
        run_script_simple("0_create_default_config.py")
    
    # Крок 1: Визначити папку введення
    success1, time1 = run_script_simple("1_folder_loader.py")
    
    # Отримуємо папку введення після роботи скрипта
    input_folder = get_input_folder()
    if not input_folder:
        logger.error("❌ Не вдалося отримати папку введення")
        return 1
    
    logger.info(f"📁 Папка введення: {input_folder}")
    
    # Отримуємо список файлів
    if not os.path.exists(input_folder):
        logger.error(f"❌ Папка {input_folder} не існує")
        return 1
        
    files_to_process = list(Path(input_folder).glob("*.txt"))
    files_to_process.sort()
    
    if not files_to_process:
        logger.error("❌ Не знайдено файлів для обробки")
        return 1
    
    logger.info(f"📁 Знайдено {len(files_to_process)} файлів для обробки")
    
    # Крок 2: Запустити браузер
    success2, time2 = run_script_simple("2_launch_gemini.py")
    if not success2:
        logger.error("❌ Не вдалося запустити браузер")
        return 1
    
    time.sleep(2)
    
    successful_files = 0
    total_file_time = 0
    
    # Обробка кожного файлу
    for file_path in files_to_process:
        file_start_time = time.time()
        logger.info(f"📄 Обробка файлу: {file_path.name}")
        
        # Крок 3: Відкрити тимчасовий чат
        success3, time3 = run_script_simple("3_open_temp_chat.py")
        time.sleep(0.3)
        
        # Крок 4: Відправити повідомлення
        if success3:
            success4, time4 = run_script_simple("4_send.py", [str(file_path)])
        else:
            success4 = False
            
        if success4:
            # Затримка для генерації відповіді
            logger.info("⏳ Очікування генерації відповіді...")
            time.sleep(4)
            
            # Крок 5: Запустити копіювання
            success5, time5 = run_script_simple("5_copy.py")
            
            if success5:
                # Отримуємо відповідь з буфера обміну
                response_text = get_response_from_clipboard()
                
                if response_text:
                    # Крок 6: Зберегти відповідь
                    success6, time6 = run_script_simple("6_save_response.py", [str(file_path), response_text])
                    
                    if success6:
                        successful_files += 1
                        file_time = time.time() - file_start_time
                        total_file_time += file_time
                        logger.info(f"✅ Файл {file_path.name} успішно оброблено")
                        time_logger.info(f"✅ Файл {file_path.name} Час обробки: {file_time:.2f} сек")
                        
                        # Крок 7: Оновити злитий файл
                        run_script_simple("7_update_merged.py")
                        time.sleep(0.2)
                    else:
                        logger.error(f"❌ Не вдалося зберегти відповідь для {file_path.name}")
                else:
                    logger.error(f"❌ Не вдалося отримати відповіді з буфера обміну для {file_path.name}")
            else:
                logger.error(f"❌ Не вдалося виконати копіювання для {file_path.name}")
        else:
            logger.error(f"❌ Не вдалося відправити файл {file_path.name}")
        
        time.sleep(0.1)
    
    # Фінальна статистика
    total_time = time.time() - total_start_time
    
    logger.info(f"📊 Обробка завершена: {successful_files}/{len(files_to_process)} файлів успішно")
    
    # Вивід загального часу виконання зеленим кольором
    print_colored_time(total_time)
    
    if successful_files == len(files_to_process):
        logger.info("🎉 Всі файли успішно оброблено!")
        return 0
    else:
        logger.warning(f"⚠️ Деякі файли не вдалося обробити")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("⏹️ Обробку перервано користувачем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Критична помилка: {e}")
        sys.exit(1)