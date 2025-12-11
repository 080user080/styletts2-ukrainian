"""
p_910_github_url_updater.py
Універсальний автономний генератор RAW посилань GitHub
Номер: 910
"""

import os
import sys
from datetime import datetime
from pathlib import Path

class UniversalURLGenerator:
    """Універсальний генератор RAW посилань GitHub"""
    
    # Конфігурація репозиторію - можна змінювати без зміни коду
    REPO_OWNER = "080user080"
    REPO_NAME = "styletts2-ukrainian"
    BRANCH = "main"
    BASE_PATH = "007_universal/kod"
    
    # Шлях для збереження результатів
    OUTPUT_FILE = "GitHub_raw_urls.txt"
    
    @staticmethod
    def _get_timestamp() -> str:
        """Повертає поточну дату та час"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def _build_raw_url(filename: str) -> str:
        """Будує RAW URL для файлу"""
        return f"https://raw.githubusercontent.com/{UniversalURLGenerator.REPO_OWNER}/{UniversalURLGenerator.REPO_NAME}/{UniversalURLGenerator.BRANCH}/{UniversalURLGenerator.BASE_PATH}/{filename}"
    
    @staticmethod
    def _get_all_modules() -> list:
        """
        Повертає список всіх модулів з їх описом
        Цей список можна редагувати без зміни коду
        """
        return [
            # Core modules
            ("Loader", "p_000_loader.py"),
            ("Config Collector", "p_010_config_collector.py"),
            ("Config Updater", "p_012_config_updater.py"),
            ("Config Tools", "p_015_config_tool.py"),
            ("Config Validator", "p_020_config_validator.py"),
            ("Deps Checker", "p_050_universal_deps_checker.py"),
            ("Error Handler", "p_060_error_handler.py"),
            ("Event Types", "p_070_event_types.py"),
            ("Event System", "p_075_events.py"),
            ("Registry", "p_080_registry.py"),
            ("GUI Manager", "p_090_gui_manager.py"),
            ("Logger", "p_100_logger.py"),
            
            # TTS modules
            ("TTS Verbalizer", "p_302_verbalizer.py"),
            ("TTS Models Loader", "p_303_tts_models.py"),
            ("TTS Wrapper", "p_304_tts_verbalizer_wrapper.py"),
            ("TTS Main GUI", "p_305_tts_gradio_main.py"),
            ("TTS Config", "p_310_tts_config.py"),
            ("TTS Engine", "p_312_tts_engine.py"),
            
            # UI modules
            ("Advanced UI Core", "p_353_advanced_ui_core.py"),
            ("UI Builder", "p_354_ui_builder.py"),
            ("UI Handlers", "p_355_ui_handlers.py"),
            ("UI Styles", "p_356_ui_styles.py"),
            ("UI Utils", "p_357_ui_utils.py"),
            
            # Helper modules
            ("AI Helper", "p_902_ai_helper.py"),
            ("Launcher", "p_996_gui_launcher.py"),
            
            # Special - цей модуль
            ("GitHub URL Generator", "p_910_github_url_updater.py"),
        ]
    
    @staticmethod
    def _log(message: str):
        """Логування в консоль"""
        timestamp = UniversalURLGenerator._get_timestamp()
        print(f"[{timestamp}] [URL Updater] {message}")
    
    @staticmethod
    def _generate_rag_navigation() -> str:
        """Генерує RAG-навігацію"""
        timestamp = UniversalURLGenerator._get_timestamp()
        
        lines = [
            f"# Автоматично згенеровано: {timestamp}",
            f"# Репозиторій: {UniversalURLGenerator.REPO_OWNER}/{UniversalURLGenerator.REPO_NAME}",
            f"# Гілка: {UniversalURLGenerator.BRANCH}",
            "",
            "1 RAG-Навігатор для ШІ",
            "Формат: Роль → RAW URL",
            "",
            "(Готово до використання в моделі 'динамічного RAG', коли ШІ завантажує тільки запитані файли.)",
            "",
        ]
        
        for module_name, filename in UniversalURLGenerator._get_all_modules():
            raw_url = UniversalURLGenerator._build_raw_url(filename)
            lines.append(f"[{module_name}] {filename}")
            lines.append(raw_url)
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def _generate_architecture_map() -> str:
        """Генерує архітектурну мапу"""
        lines = [
            "2 Архітектурна мапа проекту",
            "",
        ]
        
        # Групування за категоріями
        categories = {
            "Ядро системи": [
                ("Loader", "p_000_loader.py"),
                ("Logger", "p_100_logger.py"),
                ("Registry", "p_080_registry.py"),
            ],
            "Конфігурація": [
                ("Config Collector", "p_010_config_collector.py"),
                ("Config Updater", "p_012_config_updater.py"),
                ("Config Validator", "p_020_config_validator.py"),
            ],
            "UI/UX": [
                ("GUI Manager", "p_090_gui_manager.py"),
                ("Advanced UI Core", "p_353_advanced_ui_core.py"),
                ("UI Builder", "p_354_ui_builder.py"),
            ],
            "TTS система": [
                ("TTS Engine", "p_312_tts_engine.py"),
                ("TTS Models Loader", "p_303_tts_models.py"),
                ("TTS Config", "p_310_tts_config.py"),
            ],
            "Утиліти": [
                ("Error Handler", "p_060_error_handler.py"),
                ("Deps Checker", "p_050_universal_deps_checker.py"),
                ("AI Helper", "p_902_ai_helper.py"),
            ],
        }
        
        for category_name, modules in categories.items():
            lines.append(f"## {category_name}")
            lines.append("")
            
            for module_name, filename in modules:
                raw_url = UniversalURLGenerator._build_raw_url(filename)
                lines.append(f"• {module_name}")
                lines.append(f"  Файл: {filename}")
                lines.append(f"  RAW: {raw_url}")
                lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def _generate_info_section() -> str:
        """Генерує інформаційну секцію"""
        total_modules = len(UniversalURLGenerator._get_all_modules())
        
        lines = [
            "#" * 50,
            "ІНФОРМАЦІЯ",
            "#" * 50,
            "",
            f"Всього модулів: {total_modules}",
            f"Модуль оновлення: p_910_github_url_updater.py",
            "Файл оновлюється автоматично при кожному запуску.",
            "",
            "# Щоб змінити список модулів - редагуйте метод _get_all_modules()",
            "# Щоб змінити репозиторій - змініть змінні REPO_* вгорі класу",
            "",
            "#" * 50,
        ]
        
        return "\n".join(lines)
    
    @staticmethod
    def generate_urls_file() -> dict:
        """
        Генерує файл з усіма RAW посиланнями
        
        Returns:
            dict: Результат операції
        """
        result = {
            "success": False,
            "message": "",
            "file": UniversalURLGenerator.OUTPUT_FILE,
            "timestamp": UniversalURLGenerator._get_timestamp(),
        }
        
        try:
            UniversalURLGenerator._log("Початок генерації RAW посилань...")
            
            # Генеруємо всі секції
            rag_section = UniversalURLGenerator._generate_rag_navigation()
            arch_section = UniversalURLGenerator._generate_architecture_map()
            info_section = UniversalURLGenerator._generate_info_section()
            
            # Об'єднуємо
            full_content = f"{rag_section}\n\n{arch_section}\n\n{info_section}"
            
            # Записуємо у файл
            with open(UniversalURLGenerator.OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            # Перевіряємо
            if os.path.exists(UniversalURLGenerator.OUTPUT_FILE):
                file_size = os.path.getsize(UniversalURLGenerator.OUTPUT_FILE)
                result["success"] = True
                result["message"] = f"Успішно згенеровано ({file_size} байт)"
                result["file_size"] = file_size
                result["modules"] = len(UniversalURLGenerator._get_all_modules())
                
                UniversalURLGenerator._log(result["message"])
            else:
                result["message"] = "Помилка: файл не було створено"
                UniversalURLGenerator._log(result["message"])
                
        except Exception as e:
            result["message"] = f"Помилка: {str(e)}"
            UniversalURLGenerator._log(result["message"])
        
        return result
    
    @staticmethod
    def show_quick_status():
        """Показує короткий статус"""
        print("\n" + "=" * 60)
        print("GitHub RAW URL Generator (v910)")
        print("=" * 60)
        
        result = UniversalURLGenerator.generate_urls_file()
        
        if result["success"]:
            print(f"✅ Статус: УСПІШНО")
        else:
            print(f"❌ Статус: ПОМИЛКА")
        
        print(f"📄 Файл: {result['file']}")
        print(f"📦 Модулів: {result.get('modules', 'N/A')}")
        print(f"📊 Розмір: {result.get('file_size', 'N/A')} байт")
        print(f"🕐 Час: {result['timestamp']}")
        print("=" * 60)
        
        # Показуємо декілька прикладів
        print("\n📋 Приклади посилань:")
        print("-" * 40)
        
        examples = [
            ("Loader", "p_000_loader.py"),
            ("TTS Engine", "p_312_tts_engine.py"),
            ("Launcher", "p_996_gui_launcher.py"),
        ]
        
        for module_name, filename in examples:
            raw_url = UniversalURLGenerator._build_raw_url(filename)
            print(f"\n{module_name}:")
            print(f"{raw_url}")
        
        print("\n" + "=" * 60)


# Автоматичне виконання
if __name__ == "__main__":
    # Якщо модуль запущено напряму
    UniversalURLGenerator.show_quick_status()
    
    # Запит на перегляд файлу
    try:
        response = input("\nПереглянути згенерований файл? (y/n): ")
        if response.lower() in ['y', 'так', 'yes']:
            with open(UniversalURLGenerator.OUTPUT_FILE, 'r', encoding='utf-8') as f:
                print("\n" + "=" * 80)
                print("ЗМІСТ ФАЙЛУ GitHub_raw_urls.txt:")
                print("=" * 80)
                content = f.read()
                print(content[:1500] + "..." if len(content) > 1500 else content)
                print("=" * 80)
    except:
        pass

else:
    # Якщо модуль імпортовано - автоматично виконуємо генерацію
    result = UniversalURLGenerator.generate_urls_file()
    
    # Повідомляємо в консоль
    if result["success"]:
        print(f"[URL Updater] ✅ {result['message']}")
    else:
        print(f"[URL Updater] ❌ {result['message']}")