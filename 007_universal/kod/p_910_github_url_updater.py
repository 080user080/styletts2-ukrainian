"""
p_910_github_url_updater.py
Універсальний автономний генератор RAW посилань GitHub
Автоматично сканує всі файли в папці kod (ігнорує __pycache__ та інше)
Номер: 910
"""

import os
import sys
from datetime import datetime
from pathlib import Path

class UniversalURLGenerator:
    """Універсальний генератор RAW посилань GitHub"""
    
    # Конфігурація репозиторію
    REPO_OWNER = "080user080"
    REPO_NAME = "styletts2-ukrainian"
    BRANCH = "main"
    
    # Папка для сканування (відносно кореня репозиторію)
    REPO_FOLDER = "007_universal/kod"
    
    # Шлях для збереження результатів
    OUTPUT_FILE = "GitHub_raw_urls.txt"
    
    # Списки для ігнорування
    IGNORE_DIRS = ['__pycache__', '.git', '.vscode', '.idea', 'node_modules']
    IGNORE_FILES = ['.gitignore', '.DS_Store', 'thumbs.db', 'desktop.ini']
    IGNORE_EXTENSIONS = ['.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe']
    
    @staticmethod
    def _get_timestamp() -> str:
        """Повертає поточну дату та час"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def _build_raw_url(relative_path: str) -> str:
        """Будує RAW URL для файлу"""
        return f"https://raw.githubusercontent.com/{UniversalURLGenerator.REPO_OWNER}/{UniversalURLGenerator.REPO_NAME}/{UniversalURLGenerator.BRANCH}/{relative_path}"
    
    @staticmethod
    def _should_ignore(filepath: str, is_dir: bool = False) -> bool:
        """Перевіряє, чи потрібно ігнорувати файл/папку"""
        name = os.path.basename(filepath)
        
        if is_dir:
            return name in UniversalURLGenerator.IGNORE_DIRS
        
        # Ігноруємо приховані файли, що починаються з крапки
        if name.startswith('.'):
            return True
            
        # Ігноруємо файли з певних списків
        if name.lower() in UniversalURLGenerator.IGNORE_FILES:
            return True
            
        # Ігноруємо файли з певними розширеннями
        ext = os.path.splitext(name)[1].lower()
        if ext in UniversalURLGenerator.IGNORE_EXTENSIONS:
            return True
            
        return False
    
    @staticmethod
    def _scan_folder() -> list:
        """
        Сканує всю папку kod та повертає список всіх корисних файлів
        Повертає список кортежів: (ім'я_файлу, відносний_шлях)
        """
        files_list = []
        
        # Використовуємо поточну робочу директорію
        current_dir = os.getcwd()
        
        # Шукаємо папку kod
        kod_path = None
        
        # Спроба 1: шукаємо в поточній директорії
        if os.path.exists("kod"):
            kod_path = "kod"
        # Спроба 2: шукаємо за повним шляхом
        elif os.path.exists("007_universal/kod"):
            kod_path = "007_universal/kod"
        # Спроба 3: рекурсивний пошук
        else:
            for root, dirs, files in os.walk(current_dir):
                if "kod" in dirs:
                    kod_path = os.path.join(root, "kod")
                    break
        
        if not kod_path or not os.path.exists(kod_path):
            print(f"[ERROR] Папка 'kod' не знайдена в {current_dir}")
            print(f"[INFO] Поточний шлях: {current_dir}")
            print(f"[INFO] Спробуйте запустити з кореня проекту")
            return []
        
        print(f"[INFO] Сканування папки: {kod_path}")
        print(f"[INFO] Ігнорування: {UniversalURLGenerator.IGNORE_DIRS}")
        
        # Рекурсивно скануємо всі файли
        scanned = 0
        ignored = 0
        
        for root, dirs, files in os.walk(kod_path):
            # Видаляємо папки зі списку ігнорування
            dirs[:] = [d for d in dirs if not UniversalURLGenerator._should_ignore(d, True)]
            
            for file in files:
                scanned += 1
                
                # Перевіряємо, чи потрібно ігнорувати файл
                if UniversalURLGenerator._should_ignore(file, False):
                    ignored += 1
                    continue
                
                # Повний шлях до файлу
                full_path = os.path.join(root, file)
                
                # Відносний шлях від папки kod
                if root == kod_path:
                    relative_path = file
                else:
                    # Видаляємо шлях до kod з початку
                    rel_root = os.path.relpath(root, kod_path)
                    relative_path = os.path.join(rel_root, file)
                
                # Додаємо в список
                files_list.append((file, relative_path))
        
        # Сортуємо за іменем файлу
        files_list.sort(key=lambda x: x[0].lower())
        
        print(f"[INFO] Проскановано файлів: {scanned}")
        print(f"[INFO] Проігноровано файлів: {ignored}")
        print(f"[INFO] Знайдено корисних файлів: {len(files_list)}")
        
        return files_list
    
    @staticmethod
    def _get_module_name(filename: str) -> str:
        """
        Генерує читабельну назву модуля з імені файлу
        Приклад: p_000_loader.py -> Loader
        """
        # Видаляємо розширення
        name_without_ext = os.path.splitext(filename)[0]
        
        # Видаляємо префікс p_ та номери
        if name_without_ext.startswith("p_"):
            # Видаляємо "p_" та все до першого підкреслення після номера
            parts = name_without_ext.split("_")
            if len(parts) >= 2:
                # Знаходимо першу нечислову частину після номера
                for i, part in enumerate(parts[1:], 1):
                    if not part.isdigit() and part:
                        # З'єднуємо всі наступні частини
                        result = " ".join(parts[i:])
                        return result.replace("_", " ").title()
        
        # Якщо не вдалося розібрати, повертаємо оригінальне ім'я
        return name_without_ext.replace("_", " ").title()
    
    @staticmethod
    def _log(message: str):
        """Логування в консоль"""
        timestamp = UniversalURLGenerator._get_timestamp()
        print(f"[{timestamp}] [URL Generator] {message}")
    
    @staticmethod
    def _generate_rag_navigation(files: list) -> str:
        """Генерує RAG-навігацію зі списку файлів"""
        timestamp = UniversalURLGenerator._get_timestamp()
        
        lines = [
            "#" * 10,
            "RAG-Навігатор для ШІ",
            "#" * 10,
            "",
            f"# Автоматично згенеровано: {timestamp}",
            f"# Репозиторій: {UniversalURLGenerator.REPO_OWNER}/{UniversalURLGenerator.REPO_NAME}",
            f"# Гілка: {UniversalURLGenerator.BRANCH}",
            f"# Папка: {UniversalURLGenerator.REPO_FOLDER}",
            f"# Знайдено файлів: {len(files)}",
            "",
            "1 RAG-Навігатор для ШІ",
            "Формат: Роль → RAW URL",
            "",
            "(Готово до використання в моделі 'динамічного RAG', коли ШІ завантажує тільки запитані файли.)",
            "",
        ]
        
        for filename, relative_path in files:
            module_name = UniversalURLGenerator._get_module_name(filename)
            raw_url = UniversalURLGenerator._build_raw_url(f"{UniversalURLGenerator.REPO_FOLDER}/{relative_path}")
            lines.append(f"[{module_name}] {filename}")
            lines.append(raw_url)
            lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def _generate_architecture_map(files: list) -> str:
        """Генерує архітектурну мапу"""
        lines = [
            "#" * 10,
            "Архітектурна мапа проекту",
            "#" * 10,
            "",
            "2 Архітектурна мапа",
            "",
            "Файлова структура:",
            "",
        ]
        
        # Групуємо файли за префіксами
        prefix_groups = {}
        for filename, relative_path in files:
            # Отримуємо префікс (перші 2 символи після p_)
            if filename.startswith("p_") and len(filename) > 4:
                prefix = filename[2:4]  # Наприклад, "00" для p_000_loader.py
            else:
                prefix = "other"
            
            if prefix not in prefix_groups:
                prefix_groups[prefix] = []
            
            prefix_groups[prefix].append((filename, relative_path))
        
        # Опис префіксів
        prefix_descriptions = {
            "00": "Core - Ядро системи (завантажувачі, ініціалізація)",
            "01": "Config - Конфігурація",
            "02": "Config - Конфігурація (додатково)",
            "05": "Deps - Залежності",
            "06": "Error - Обробка помилок",
            "07": "Events - Система подій",
            "08": "Registry - Реєстр",
            "09": "GUI - Графічний інтерфейс",
            "10": "Logger - Логування",
            "30": "TTS - Текст в мову",
            "35": "UI - Користувацький інтерфейс",
            "90": "AI - Штучний інтелект",
            "99": "Launcher - Запуск системи",
            "other": "Інші файли",
        }
        
        # Сортуємо групи за ключем
        for prefix in sorted(prefix_groups.keys()):
            group_files = prefix_groups[prefix]
            
            # Опис групи
            description = prefix_descriptions.get(prefix, f"Група {prefix}")
            lines.append(f"## {description} ({len(group_files)} файлів)")
            lines.append("")
            
            for filename, relative_path in group_files:
                module_name = UniversalURLGenerator._get_module_name(filename)
                raw_url = UniversalURLGenerator._build_raw_url(f"{UniversalURLGenerator.REPO_FOLDER}/{relative_path}")
                lines.append(f"• {module_name}")
                lines.append(f"  Файл: {filename}")
                if relative_path != filename:
                    lines.append(f"  Шлях: {relative_path}")
                lines.append(f"  RAW: {raw_url}")
                lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def _generate_info_section(files_count: int) -> str:
        """Генерує інформаційну секцію"""
        lines = [
            "#" * 10,
            "ІНФОРМАЦІЯ ПРО ГЕНЕРАЦІЮ",
            "#" * 10,
            "",
            f"Загальна кількість файлів: {files_count}",
            f"Дата генерації: {UniversalURLGenerator._get_timestamp()}",
            f"Репозиторій: {UniversalURLGenerator.REPO_OWNER}/{UniversalURLGenerator.REPO_NAME}",
            f"Гілка: {UniversalURLGenerator.BRANCH}",
            f"Папка: {UniversalURLGenerator.REPO_FOLDER}",
            "",
            "АВТОМАТИЧНА ГЕНЕРАЦІЯ",
            "Файл автоматично оновлюється при кожному запуску системи.",
            "Модуль сканує всі файли в папці 'kod' і генерує RAW посилання.",
            "",
            "ІГНОРУВАННЯ:",
            f"• Папки: {', '.join(UniversalURLGenerator.IGNORE_DIRS)}",
            f"• Файли: {', '.join(UniversalURLGenerator.IGNORE_FILES)}",
            f"• Розширення: {', '.join(UniversalURLGenerator.IGNORE_EXTENSIONS)}",
            "",
            "МОДУЛЬ: p_910_github_url_updater.py",
            "Версія: 3.0 (автоматичне сканування з ігноруванням)",
            "",
            "#" * 10,
            "Даю дозвіл відкривати всі посилання які я тут виклав.",
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
            "files_count": 0,
        }
        
        try:
            UniversalURLGenerator._log("Початок сканування папки 'kod'...")
            
            # Скануємо всі файли
            files = UniversalURLGenerator._scan_folder()
            
            if not files:
                result["message"] = "Не знайдено жодного корисного файлу в папці 'kod'"
                UniversalURLGenerator._log(result["message"])
                return result
            
            result["files_count"] = len(files)
            UniversalURLGenerator._log(f"Знайдено корисних файлів: {len(files)}")
            
            # Генеруємо всі секції
            rag_section = UniversalURLGenerator._generate_rag_navigation(files)
            arch_section = UniversalURLGenerator._generate_architecture_map(files)
            info_section = UniversalURLGenerator._generate_info_section(len(files))
            
            # Об'єднуємо
            full_content = f"{rag_section}\n\n{arch_section}\n\n{info_section}"
            
            # Записуємо у файл
            with open(UniversalURLGenerator.OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            # Перевіряємо
            if os.path.exists(UniversalURLGenerator.OUTPUT_FILE):
                file_size = os.path.getsize(UniversalURLGenerator.OUTPUT_FILE)
                result["success"] = True
                result["message"] = f"Успішно згенеровано ({file_size} байт, {len(files)} файлів)"
                result["file_size"] = file_size
                
                UniversalURLGenerator._log(result["message"])
            else:
                result["message"] = "Помилка: файл не було створено"
                UniversalURLGenerator._log(result["message"])
                
        except Exception as e:
            result["message"] = f"Помилка: {str(e)}"
            UniversalURLGenerator._log(result["message"])
        
        return result
    
    @staticmethod
    def show_status():
        """Показує статус генерації"""
        print("\n" + "=" * 70)
        print("GitHub RAW URL Generator (v910 - Auto Scan with Ignore)")
        print("=" * 70)
        
        result = UniversalURLGenerator.generate_urls_file()
        
        if result["success"]:
            print(f"✅ Статус: УСПІШНО")
        else:
            print(f"❌ Статус: ПОМИЛКА")
        
        print(f"📄 Вихідний файл: {result['file']}")
        print(f"📦 Корисних файлів: {result['files_count']}")
        
        if result.get('file_size'):
            print(f"📊 Розмір файлу: {result['file_size']} байт")
        
        print(f"🕐 Час генерації: {result['timestamp']}")
        
        # Показуємо, що ігнорується
        print(f"🚫 Ігнорується: __pycache__, .git, .pyc та інше")
        
        print("=" * 70)
        
        # Показуємо перші 5 файлів як приклад
        if result["files_count"] > 0:
            print("\n📋 Перші 5 файлів зі списку:")
            print("-" * 40)
            
            # Отримуємо список файлів ще раз для демонстрації
            files = UniversalURLGenerator._scan_folder()
            if files:
                for i, (filename, relative_path) in enumerate(files[:5]):
                    module_name = UniversalURLGenerator._get_module_name(filename)
                    print(f"\n{i+1}. {module_name}:")
                    print(f"   Файл: {filename}")
                    if relative_path != filename:
                        print(f"   Шлях: {relative_path}")
        
        print("\n" + "=" * 70)
        print(f"📁 Файл '{UniversalURLGenerator.OUTPUT_FILE}' готовий до використання!")
        print("=" * 70)


# Автоматичне виконання
if __name__ == "__main__":
    # Якщо модуль запущено напряму
    UniversalURLGenerator.show_status()
    
    # Запит на перегляд файлу
    try:
        response = input("\n📄 Переглянути згенерований файл? (y/n): ")
        if response.lower() in ['y', 'так', 'yes']:
            if os.path.exists(UniversalURLGenerator.OUTPUT_FILE):
                with open(UniversalURLGenerator.OUTPUT_FILE, 'r', encoding='utf-8') as f:
                    print("\n" + "=" * 80)
                    print("ЗМІСТ ФАЙЛУ GitHub_raw_urls.txt:")
                    print("=" * 80)
                    content = f.read()
                    # Показуємо тільки перші 2000 символів
                    print(content[:2000] + "..." if len(content) > 2000 else content)
                    print("=" * 80)
            else:
                print("❌ Файл не знайдено.")
    except:
        pass

else:
    # Якщо модуль імпортовано - автоматично виконуємо генерацію
    result = UniversalURLGenerator.generate_urls_file()
    
    # Повідомляємо в консоль
    if result["success"]:
        print(f"[URL Generator] ✅ {result['message']}")
    else:
        print(f"[URL Generator] ❌ {result['message']}")