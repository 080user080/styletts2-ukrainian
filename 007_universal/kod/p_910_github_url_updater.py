"""
p_910_github_url_updater.py
Автономний модуль для оновлення RAW посилань GitHub при запуску системи
Номер: 910
Версія: 1.0
"""

import os
from datetime import datetime
from pathlib import Path

class GitHubURLUpdater:
    """Автономний оновлювач RAW посилань GitHub"""
    
    # Конфігурація репозиторію
    REPO_OWNER = "080user080"
    REPO_NAME = "styletts2-ukrainian"
    BRANCH = "main"
    BASE_PATH = "007_universal/kod"
    
    # Шляхи файлів
    OUTPUT_FILE = "GitHub_raw_urls.txt"
    LOG_FILE = "system.log"  # Основний лог проекту
    
    # Список всіх модулів проекту
    MODULES = [
        # Core (0-199)
        ("Loader", "p_000_loader.py", "Основний завантажувач модулів"),
        ("Config Collector", "p_010_config_collector.py", "Збір конфігурації"),
        ("Config Updater", "p_012_config_updater.py", "Оновлення конфігурації"),
        ("Config Tools", "p_015_config_tool.py", "Інструменти конфігурації"),
        ("Config Validator", "p_020_config_validator.py", "Валідація конфігурації"),
        ("Deps Checker", "p_050_universal_deps_checker.py", "Перевірка залежностей"),
        ("Error Handler", "p_060_error_handler.py", "Обробка помилок"),
        ("Event Types", "p_070_event_types.py", "Типи подій"),
        ("Event System", "p_075_events.py", "Система подій"),
        ("Registry", "p_080_registry.py", "Реєстр компонентів"),
        ("GUI Manager", "p_090_gui_manager.py", "Менеджер GUI"),
        ("Logger", "p_100_logger.py", "Система логування"),
        
        # TTS (300-349)
        ("TTS Verbalizer", "p_302_verbalizer.py", "Вербалізатор TTS"),
        ("TTS Models Loader", "p_303_tts_models.py", "Завантажувач моделей TTS"),
        ("TTS Wrapper", "p_304_tts_verbalizer_wrapper.py", "Обгортка TTS"),
        ("TTS Main GUI", "p_305_tts_gradio_main.py", "Головний GUI TTS"),
        ("TTS Config", "p_310_tts_config.py", "Конфігурація TTS"),
        ("TTS Engine", "p_312_tts_engine.py", "Двигун TTS"),
        
        # UI (350-399)
        ("Advanced UI Core", "p_353_advanced_ui_core.py", "Ядро розширеного UI"),
        ("UI Builder", "p_354_ui_builder.py", "Будівельник UI"),
        ("UI Handlers", "p_355_ui_handlers.py", "Обробники UI"),
        ("UI Styles", "p_356_ui_styles.py", "Стилі UI"),
        ("UI Utils", "p_357_ui_utils.py", "Утиліти UI"),
        
        # AI Helper (900-949)
        ("AI Helper", "p_902_ai_helper.py", "AI помічник"),
        
        # Launcher (990-999)
        ("Launcher", "p_996_gui_launcher.py", "Запускач GUI"),
        
        # Спеціальні (910)
        ("GitHub URL Updater", "p_910_github_url_updater.py", "Оновлювач RAW посилань"),
    ]
    
    @staticmethod
    def _get_timestamp() -> str:
        """Повертає поточну дату та час у форматі рядка"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def _build_raw_url(filename: str) -> str:
        """Будує RAW URL для файлу"""
        return f"https://raw.githubusercontent.com/{GitHubURLUpdater.REPO_OWNER}/{GitHubURLUpdater.REPO_NAME}/{GitHubURLUpdater.BRANCH}/{GitHubURLUpdater.BASE_PATH}/{filename}"
    
    @staticmethod
    def _log_to_console(message: str, message_type: str = "INFO"):
        """Логування повідомлення в консоль"""
        timestamp = GitHubURLUpdater._get_timestamp()
        
        # Кольорові коди для консолі
        colors = {
            "INFO": "\033[94m",    # Синій
            "SUCCESS": "\033[92m",  # Зелений
            "WARNING": "\033[93m",  # Жовтий
            "ERROR": "\033[91m",    # Червоний
            "RESET": "\033[0m",     # Скидання
        }
        
        color = colors.get(message_type, colors["INFO"])
        print(f"{color}[{timestamp}] [{message_type}] {message}{colors['RESET']}")
    
    @staticmethod
    def _log_to_file(message: str, message_type: str = "INFO"):
        """Логування повідомлення у файл system.log"""
        try:
            timestamp = GitHubURLUpdater._get_timestamp()
            log_entry = f"[{timestamp}] [{message_type}] {message}\n"
            
            # Додаємо запис у кінець файлу
            with open(GitHubURLUpdater.LOG_FILE, 'a', encoding='utf-8') as log_file:
                log_file.write(log_entry)
        except Exception as e:
            # Якщо не вдалося записати в файл, пишемо в консоль
            print(f"Помилка логування в файл: {e}")
    
    @staticmethod
    def _log(message: str, message_type: str = "INFO"):
        """Комбіноване логування (консоль + файл)"""
        GitHubURLUpdater._log_to_console(message, message_type)
        GitHubURLUpdater._log_to_file(message, message_type)
    
    @staticmethod
    def _generate_rag_section() -> str:
        """Генерує секцію RAG-навігатора"""
        lines = []
        
        lines.append("=" * 80)
        lines.append("RAG-Навігатор для ШІ")
        lines.append("=" * 80)
        lines.append("")
        lines.append("1 RAG-Навігатор для ШІ")
        lines.append("Формат: Роль → RAW URL")
        lines.append("")
        lines.append("(Готово до використання в моделі 'динамічного RAG', коли ШІ завантажує тільки запитані файли.)")
        lines.append("")
        
        for module_name, filename, _ in GitHubURLUpdater.MODULES:
            raw_url = GitHubURLUpdater._build_raw_url(filename)
            lines.append(f"[{module_name}] {filename}")
            lines.append(raw_url)
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def _generate_architecture_section() -> str:
        """Генерує секцію архітектурної мапи"""
        lines = []
        
        lines.append("=" * 80)
        lines.append("Архітектурна мапа проекту")
        lines.append("=" * 80)
        lines.append("")
        lines.append("2 Архітектурна мапа")
        lines.append("")
        
        # Групуємо модулі за категоріями
        categories = {
            "Ядро системи": ["Loader", "Logger", "Registry", "Error Handler", "Event System"],
            "Конфігурація": ["Config Collector", "Config Updater", "Config Tools", "Config Validator"],
            "Графічний інтерфейс": ["GUI Manager", "Advanced UI Core", "UI Builder", "UI Handlers"],
            "TTS система": ["TTS Engine", "TTS Verbalizer", "TTS Models Loader", "TTS Config"],
            "Утиліти": ["Deps Checker", "AI Helper", "GitHub URL Updater"],
            "Запуск": ["Launcher"],
        }
        
        for category, module_names in categories.items():
            lines.append(f"## {category}")
            lines.append("")
            
            for module_name in module_names:
                # Шукаємо модуль за іменем
                for m_name, filename, description in GitHubURLUpdater.MODULES:
                    if m_name == module_name:
                        raw_url = GitHubURLUpdater._build_raw_url(filename)
                        lines.append(f"### {m_name}")
                        lines.append(f"Опис: {description}")
                        lines.append(f"Файл: {filename}")
                        lines.append(f"RAW URL: {raw_url}")
                        lines.append("")
                        break
        
        return "\n".join(lines)
    
    @staticmethod
    def _generate_info_section() -> str:
        """Генерує інформаційну секцію"""
        timestamp = GitHubURLUpdater._get_timestamp()
        total_modules = len(GitHubURLUpdater.MODULES)
        
        lines = []
        lines.append("=" * 80)
        lines.append("Інформація про генерацію")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Дата генерації: {timestamp}")
        lines.append(f"Загальна кількість модулів: {total_modules}")
        lines.append(f"Репозиторій: {GitHubURLUpdater.REPO_OWNER}/{GitHubURLUpdater.REPO_NAME}")
        lines.append(f"Гілка: {GitHubURLUpdater.BRANCH}")
        lines.append(f"Базова директорія: {GitHubURLUpdater.BASE_PATH}")
        lines.append("")
        lines.append("Файл оновлюється автоматично при кожному запуску системи.")
        lines.append("Модуль: p_910_github_url_updater.py")
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    @staticmethod
    def update_urls() -> dict:
        """
        Оновлює файл з RAW посиланнями
        
        Returns:
            dict: Результат операції
        """
        result = {
            "success": False,
            "message": "",
            "output_file": GitHubURLUpdater.OUTPUT_FILE,
            "timestamp": GitHubURLUpdater._get_timestamp(),
            "modules_count": len(GitHubURLUpdater.MODULES),
        }
        
        try:
            # Логуємо початок оновлення
            GitHubURLUpdater._log("Початок оновлення RAW посилань GitHub", "INFO")
            
            # Генеруємо всі секції
            rag_section = GitHubURLUpdater._generate_rag_section()
            arch_section = GitHubURLUpdater._generate_architecture_section()
            info_section = GitHubURLUpdater._generate_info_section()
            
            # Об'єднуємо всі секції
            full_content = f"{rag_section}\n\n{arch_section}\n\n{info_section}"
            
            # Записуємо у файл
            with open(GitHubURLUpdater.OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            # Перевіряємо, чи файл створено
            if os.path.exists(GitHubURLUpdater.OUTPUT_FILE):
                file_size = os.path.getsize(GitHubURLUpdater.OUTPUT_FILE)
                
                result["success"] = True
                result["message"] = f"Файл успішно оновлено ({file_size} байт)"
                result["file_size"] = file_size
                
                # Логуємо успіх
                GitHubURLUpdater._log(result["message"], "SUCCESS")
            else:
                result["message"] = "Файл не було створено"
                GitHubURLUpdater._log(result["message"], "ERROR")
                
        except Exception as e:
            result["message"] = f"Помилка: {str(e)}"
            GitHubURLUpdater._log(result["message"], "ERROR")
        
        return result
    
    @staticmethod
    def show_status():
        """Показує статус оновлення та інформацію про файл"""
        print("\n" + "=" * 60)
        print("GitHub RAW URL Updater (v910)")
        print("=" * 60)
        
        # Виконуємо оновлення
        result = GitHubURLUpdater.update_urls()
        
        # Виводимо статус
        if result["success"]:
            print(f"✅ Статус: УСПІШНО")
        else:
            print(f"❌ Статус: ПОМИЛКА")
        
        print(f"📝 Повідомлення: {result['message']}")
        print(f"📁 Вихідний файл: {result['output_file']}")
        print(f"📦 Модулів: {result['modules_count']}")
        print(f"🕐 Час: {result['timestamp']}")
        
        # Додаткова інформація про файл
        if result.get("file_size"):
            print(f"📊 Розмір файлу: {result['file_size']} байт")
        
        print("=" * 60)
        
        # Показуємо декілька прикладів посилань
        print("\n📋 Приклади RAW посилань:")
        print("-" * 40)
        
        # Вибираємо декілька важливих модулів для демонстрації
        important_modules = [
            ("Loader", "p_000_loader.py"),
            ("TTS Engine", "p_312_tts_engine.py"),
            ("Launcher", "p_996_gui_launcher.py"),
            ("GitHub URL Updater", "p_910_github_url_updater.py"),
        ]
        
        for module_name, filename in important_modules:
            raw_url = GitHubURLUpdater._build_raw_url(filename)
            print(f"\n{module_name}:")
            print(f"{filename}")
            print(f"{raw_url}")
        
        print("\n" + "=" * 60)
        print(f"Файл '{GitHubURLUpdater.OUTPUT_FILE}' готовий до використання!")
        print("=" * 60)


# Автоматичне виконання при запуску модуля
if __name__ == "__main__":
    # Запуск у режимі автономного виконання
    GitHubURLUpdater.show_status()
    
    # Чекаємо натискання Enter перед закриттям
    input("\nНатисніть Enter для завершення...")

else:
    # Якщо модуль імпортовано - автоматично оновлюємо посилання
    print(f"\n[GitHubURLUpdater] Запуск оновлення RAW посилань...")
    result = GitHubURLUpdater.update_urls()
    
    if result["success"]:
        print(f"[GitHubURLUpdater] ✅ {result['message']}")
    else:
        print(f"[GitHubURLUpdater] ❌ {result['message']}")