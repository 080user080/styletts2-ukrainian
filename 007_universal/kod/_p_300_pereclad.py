"""
Модуль P_300: Pereclad - система автоматичного перекладу через Google Gemini
Інтеграція KOD_pereclad.py в модульну систему
"""
import os
import sys
import subprocess
import importlib
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class PerecladConfig(BaseModel):
    """Модель конфігурації для модуля перекладу"""
    enabled: bool = Field(False, description="Чи увімкнено модуль перекладу")
    gemini_url: str = Field("https://gemini.google.com/", description="URL сторінки Gemini")
    output_folder: str = Field("output", description="Вихідна папка для перекладених файлів")
    merged_filename: str = Field("merged_UKR.txt", description="Ім'я об'єднаного файлу")
    numeric_prefix_regex: str = Field(r"^\d+", description="Регулярний вираз для числового префіксу")
    template_message: str = Field(
        "Зробити адаптивний переклад максимально точний. У відповіді тільки перекладений текст без жодних твоїх питань побажань чи вставок.",
        description="Шаблон повідомлення для Gemini"
    )
    hotkey_new_chat: str = Field("temp_chat_button", description="Метод створення нового чату")
    on_bad_response: str = Field("mark_for_manual", description="Дія при поганий відповіді: retry, mark_for_manual, skip")
    manual_tag: str = Field("_check", description="Тег для файлів, що потребують перевірки")
    max_retries: int = Field(2, description="Максимальна кількість спроб")
    page_load_timeout: int = Field(30, description="Таймаут завантаження сторінки (секунди)")
    response_timeout: int = Field(10, description="Таймаут очікування відповіді (секунди)")
    log_formats: list = Field(["txt", "json"], description="Формати лог-файлів")
    connect_via_cdp: bool = Field(True, description="Використовувати CDP для підключення до Chrome")
    cdp_port: int = Field(9222, description="Порт для CDP")
    chrome_executable_path: str = Field(
        r"C:\Program Files\Google\Chrome\Application\chrome.exe", 
        description="Шлях до Chrome"
    )
    chrome_user_data_dir: str = Field(
        r"C:\Temp\chrome_debug_profile", 
        description="Шлях до профілю Chrome"
    )
    auto_launch_chrome: bool = Field(True, description="Автоматичний запуск Chrome")
    chrome_launch_timeout: int = Field(20, description="Таймаут запуску Chrome (секунди)")
    input_folder: str = Field("", description="Вхідна папка з файлами для перекладу")


def prepare_config_models() -> Dict[str, Any]:
    """
    Повертає моделі Pydantic для конфігурації перекладу
    """
    return {"pereclad": PerecladConfig}


def _install_dependencies(logger) -> bool:
    """
    Автоматично встановлює необхідні залежності для модуля перекладу
    Повертає True якщо всі залежності доступні
    """
    required_packages = {
        'playwright': 'playwright',
        'yaml': 'pyyaml', 
        'pyperclip': 'pyperclip'
    }
    
    missing_packages = []
    
    # Перевіряємо наявність бібліотек
    for import_name, package_name in required_packages.items():
        try:
            importlib.import_module(import_name)
            logger.debug(f"✅ Бібліотека {package_name} вже встановлена")
        except ImportError:
            missing_packages.append(package_name)
    
    # Встановлюємо відсутні бібліотеки
    if missing_packages:
        logger.warning(f"Встановлення відсутніх залежностей: {', '.join(missing_packages)}")
        try:
            for package in missing_packages:
                logger.info(f"📦 Встановлення {package}...")
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", package
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Після встановлення playwright, інсталюємо браузери
            if 'playwright' in missing_packages:
                logger.info("🌐 Встановлення браузерів для playwright...")
                subprocess.check_call([
                    sys.executable, "-m", "playwright", "install"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
            logger.info("✅ Всі залежності успішно встановлено")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Помилка встановлення залежностей: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Неочікувана помилка при встановленні: {e}")
            return False
    
    return True


def _run_pereclad_module(config: dict, logger):
    """
    Запускає головну логіку перекладу з KOD_pereclad.py
    """
    try:
        # Додаємо шлях до кореня проекту для імпорту KOD_pereclad
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        # Імпортуємо модуль перекладу
        from KOD_pereclad import process_all
        
        logger.info("🚀 Запуск модуля перекладу...")
        
        # Викликаємо головну функцію перекладу
        process_all(config)
        
        logger.info("✅ Модуль перекладу успішно завершив роботу")
        
    except ImportError as e:
        logger.error(f"❌ Не вдалося імпортувати KOD_pereclad: {e}")
        logger.info("📝 Переконайтеся, що KOD_pereclad.py знаходиться в корені проекту")
        raise
    except Exception as e:
        logger.error(f"❌ Помилка виконання модуля перекладу: {e}")
        raise
    finally:
        # Видаляємо доданий шлях
        if str(project_root) in sys.path:
            sys.path.remove(str(project_root))


def initialize(app_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Ініціалізує модуль перекладу
    """
    config = app_context['config']
    logger = app_context['logger'].getChild('Pereclad')
    
    # Перевірка, чи увімкнено модуль
    if not hasattr(config, 'pereclad') or not config.pereclad.enabled:
        logger.info("Модуль перекладу вимкнено в конфігурації")
        return None
    
    pereclad_config = config.pereclad
    logger.info("🔧 Ініціалізація модуля перекладу...")
    
    # Перевіряємо та встановлюємо залежності
    if not _install_dependencies(logger):
        logger.error("❌ Не вдалося встановити залежності для модуля перекладу")
        return None
    
    try:
        # Запускаємо модуль перекладу
        _run_pereclad_module(pereclad_config.dict(), logger)
        
        # Повертаємо результат для контексту (опціонально)
        return {
            "status": "completed",
            "module": "pereclad"
        }
        
    except Exception as e:
        logger.error(f"❌ Критична помилка в модулі перекладу: {e}")
        return {
            "status": "error",
            "module": "pereclad",
            "error": str(e)
        }