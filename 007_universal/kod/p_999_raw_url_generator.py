"""
Модуль для генерації RAW посилань на файли у GitHub репозиторії
Номер: 999
"""

import os
import re
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse, urljoin


class GitHubRawURLGenerator:
    """Генератор RAW посилань для GitHub репозиторіїв"""
    
    # Шаблони для посилань
    GITHUB_RAW_PATTERN = "https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
    GITHUB_WEB_PATTERN = "https://github.com/{owner}/{repo}/blob/{branch}/{path}"
    
    @staticmethod
    def extract_repo_info(url: str) -> Tuple[str, str, str, str]:
        """
        Вилучає інформацію про репозиторій з URL
        
        Args:
            url: URL репозиторію або файлу
            
        Returns:
            Tuple: (власник, репозиторій, гілка, шлях)
        """
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        
        owner = ""
        repo = ""
        branch = "main"  # за замовчуванням
        file_path = ""
        
        if len(path_parts) >= 2:
            owner = path_parts[0]
            repo = path_parts[1]
            
            if len(path_parts) >= 5 and path_parts[2] == 'blob':
                # Веб-посилання GitHub
                branch = path_parts[3]
                file_path = '/'.join(path_parts[4:])
            elif len(path_parts) >= 4 and path_parts[2] == 'tree':
                # Посилання на директорію
                branch = path_parts[3]
                file_path = '/'.join(path_parts[4:]) if len(path_parts) > 4 else ""
            elif len(path_parts) > 2:
                # Спроба визначити гілку та шлях
                branch = path_parts[2] if len(path_parts) > 2 else "main"
                file_path = '/'.join(path_parts[3:]) if len(path_parts) > 3 else ""
        
        return owner, repo, branch, file_path
    
    @staticmethod
    def create_raw_url(owner: str, repo: str, branch: str, file_path: str) -> str:
        """
        Створює RAW URL для файлу
        
        Args:
            owner: Власник репозиторію
            repo: Назва репозиторію
            branch: Гілка (main, master тощо)
            file_path: Шлях до файлу в репозиторії
            
        Returns:
            RAW URL для файлу
        """
        # Видаляємо початковий слеш, якщо є
        if file_path.startswith('/'):
            file_path = file_path[1:]
        
        return GitHubRawURLGenerator.GITHUB_RAW_PATTERN.format(
            owner=owner,
            repo=repo,
            branch=branch,
            path=file_path
        )
    
    @staticmethod
    def convert_web_to_raw(web_url: str) -> str:
        """
        Конвертує веб-посилання GitHub у RAW посилання
        
        Args:
            web_url: Веб-посилання на файл у GitHub
            
        Returns:
            RAW URL для файлу
        """
        owner, repo, branch, file_path = GitHubRawURLGenerator.extract_repo_info(web_url)
        
        if not owner or not repo:
            raise ValueError(f"Неможливо визначити репозиторій з URL: {web_url}")
        
        return GitHubRawURLGenerator.create_raw_url(owner, repo, branch, file_path)
    
    @staticmethod
    def generate_navigation_format(module_name: str, raw_url: str) -> str:
        """
        Генерує запис у форматі навігації для ШІ
        
        Args:
            module_name: Назва модуля
            raw_url: RAW URL файлу
            
        Returns:
            Рядок у форматі навігації
        """
        # Вилучаємо ім'я файлу з URL
        file_name = os.path.basename(raw_url)
        return f"[{module_name}] {file_name}\n{raw_url}"
    
    @staticmethod
    def create_rag_navigation(files_dict: Dict[str, str], title: str = None) -> str:
        """
        Створює повний текст RAG-навігації для ШІ
        
        Args:
            files_dict: Словник {назва_модуля: URL_файлу}
            title: Заголовок навігації
            
        Returns:
            Текст навігації у потрібному форматі
        """
        lines = []
        
        if title:
            lines.append(title)
        
        for i, (module_name, file_url) in enumerate(files_dict.items()):
            # Конвертуємо у RAW URL, якщо потрібно
            if 'raw.githubusercontent.com' not in file_url:
                try:
                    raw_url = GitHubRawURLGenerator.convert_web_to_raw(file_url)
                except ValueError:
                    raw_url = file_url  # Якщо не вдалося конвертувати, залишаємо оригінал
            else:
                raw_url = file_url
            
            lines.append(GitHubRawURLGenerator.generate_navigation_format(module_name, raw_url))
            
            # Додаємо порожній рядок між записами (крім останнього)
            if i < len(files_dict) - 1:
                lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def parse_existing_navigation(navigation_text: str) -> Dict[str, str]:
        """
        Парсить існуючий текст навігації у словник
        
        Args:
            navigation_text: Текст навігації
            
        Returns:
            Словник {назва_модуля: URL_файлу}
        """
        result = {}
        lines = navigation_text.strip().split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Шукаємо рядки з назвами модулів
            if line.startswith('[') and ']' in line:
                # Вилучаємо назву модуля
                end_bracket = line.find(']')
                module_name = line[1:end_bracket].strip()
                
                # Шукаємо наступний рядок з URL
                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    if url.startswith('http'):
                        result[module_name] = url
                        i += 1  # Пропускаємо URL рядок
            i += 1
        
        return result
    
    @staticmethod
    def create_architectural_map(repo_url: str, structure: List[Tuple[str, str]]) -> str:
        """
        Створює архітектурну мапу проекту
        
        Args:
            repo_url: URL репозиторію
            structure: Список кортежів (назва_компонента, шлях_до_файлу)
            
        Returns:
            Текст архітектурної мапи
        """
        # Вилучаємо базову інформацію про репозиторій
        owner, repo, branch, _ = GitHubRawURLGenerator.extract_repo_info(repo_url)
        
        lines = []
        lines.append("2 Архітектурна мапа\n")
        
        for component_name, file_path in structure:
            if file_path:
                raw_url = GitHubRawURLGenerator.create_raw_url(owner, repo, branch, file_path)
                lines.append(f"{component_name}")
                lines.append(f"Файл: {os.path.basename(file_path)}")
                lines.append(f"RAW: {raw_url}\n")
            else:
                lines.append(f"{component_name}\n")
        
        return "\n".join(lines)


class ProjectURLManager:
    """Менеджер для роботи з URL проекту"""
    
    def __init__(self, repo_owner: str, repo_name: str, branch: str = "main"):
        """
        Ініціалізація менеджера
        
        Args:
            repo_owner: Власник репозиторію
            repo_name: Назва репозиторію
            branch: Гілка репозиторію
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.branch = branch
        self.generator = GitHubRawURLGenerator()
    
    def get_raw_url(self, file_path: str) -> str:
        """
        Отримати RAW URL для файлу
        
        Args:
            file_path: Шлях до файлу в репозиторії
            
        Returns:
            RAW URL
        """
        return self.generator.create_raw_url(
            self.repo_owner,
            self.repo_name,
            self.branch,
            file_path
        )
    
    def create_project_navigation(self, modules: List[Tuple[str, str]]) -> str:
        """
        Створити навігацію для всього проекту
        
        Args:
            modules: Список кортежів (назва_модуля, шлях_до_файлу)
            
        Returns:
            Текст навігації
        """
        files_dict = {}
        
        for module_name, file_path in modules:
            raw_url = self.get_raw_url(file_path)
            files_dict[module_name] = raw_url
        
        # Додаємо архітектурну мапу
        structure = [
            ("Завантажувач", "007_universal/kod/p_000_loader.py"),
            ("Конфігураційний менеджер", "007_universal/kod/p_010_config_collector.py"),
            ("Менеджер GUI", "007_universal/kod/p_090_gui_manager.py"),
            ("Логер", "007_universal/kod/p_100_logger.py"),
            ("TTS Двигун", "007_universal/kod/p_312_tts_engine.py"),
            ("Запускач", "007_universal/kod/p_996_gui_launcher.py"),
        ]
        
        repo_url = f"https://github.com/{self.repo_owner}/{self.repo_name}"
        architectural_map = self.generator.create_architectural_map(repo_url, structure)
        
        rag_nav = self.generator.create_rag_navigation(
            files_dict,
            title="1 RAG-Навігатор для ШІ\nФормат: Роль → RAW URL\n\n(Готово до використання в моделі 'динамічного RAG', коли ШІ завантажує тільки запитані файли.)"
        )
        
        return f"{rag_nav}\n\n{architectural_map}"
    
    def generate_all_urls(self, base_dir: str = "007_universal/kod") -> Dict[str, str]:
        """
        Генерує URL для всіх Python файлів у директорії
        
        Args:
            base_dir: Базова директорія в репозиторії
            
        Returns:
            Словник {ім'я_файлу: RAW_URL}
        """
        # У реальному використанні тут буде сканування директорії
        # Для прикладу повертаємо статичний список
        
        common_files = [
            "p_000_loader.py",
            "p_010_config_collector.py",
            "p_012_config_updater.py",
            "p_015_config_tool.py",
            "p_020_config_validator.py",
            "p_050_universal_deps_checker.py",
            "p_060_error_handler.py",
            "p_070_event_types.py",
            "p_075_events.py",
            "p_080_registry.py",
            "p_090_gui_manager.py",
            "p_100_logger.py",
            "p_302_verbalizer.py",
            "p_303_tts_models.py",
            "p_304_tts_verbalizer_wrapper.py",
            "p_305_tts_gradio_main.py",
            "p_310_tts_config.py",
            "p_312_tts_engine.py",
            "p_353_advanced_ui_core.py",
            "p_354_ui_builder.py",
            "p_355_ui_handlers.py",
            "p_356_ui_styles.py",
            "p_357_ui_utils.py",
            "p_902_ai_helper.py",
            "p_996_gui_launcher.py",
        ]
        
        result = {}
        for filename in common_files:
            file_path = f"{base_dir}/{filename}" if base_dir else filename
            result[filename] = self.get_raw_url(file_path)
        
        return result


def main():
    """Приклад використання модуля"""
    
    # Ініціалізація менеджера для конкретного репозиторію
    manager = ProjectURLManager(
        repo_owner="080user080",
        repo_name="styletts2-ukrainian",
        branch="main"
    )
    
    # Приклад 1: Отримання RAW URL для конкретного файлу
    raw_url = manager.get_raw_url("007_universal/kod/p_000_loader.py")
    print(f"Приклад RAW URL: {raw_url}\n")
    
    # Приклад 2: Створення навігації для проекту
    modules_list = [
        ("Loader", "007_universal/kod/p_000_loader.py"),
        ("Config Collector", "007_universal/kod/p_010_config_collector.py"),
        ("Config Updater", "007_universal/kod/p_012_config_updater.py"),
        ("Config Tools", "007_universal/kod/p_015_config_tool.py"),
        ("Config Validator", "007_universal/kod/p_020_config_validator.py"),
        ("Deps Checker", "007_universal/kod/p_050_universal_deps_checker.py"),
        ("Error Handler", "007_universal/kod/p_060_error_handler.py"),
        ("Event Types", "007_universal/kod/p_070_event_types.py"),
        ("Event System", "007_universal/kod/p_075_events.py"),
        ("Registry", "007_universal/kod/p_080_registry.py"),
        ("GUI Manager", "007_universal/kod/p_090_gui_manager.py"),
        ("Logger", "007_universal/kod/p_100_logger.py"),
        ("TTS Verbalizer", "007_universal/kod/p_302_verbalizer.py"),
        ("TTS Models Loader", "007_universal/kod/p_303_tts_models.py"),
        ("TTS Wrapper", "007_universal/kod/p_304_tts_verbalizer_wrapper.py"),
        ("TTS Main GUI", "007_universal/kod/p_305_tts_gradio_main.py"),
        ("TTS Config", "007_universal/kod/p_310_tts_config.py"),
        ("TTS Engine", "007_universal/kod/p_312_tts_engine.py"),
        ("Advanced UI Core", "007_universal/kod/p_353_advanced_ui_core.py"),
        ("UI Builder", "007_universal/kod/p_354_ui_builder.py"),
        ("UI Handlers", "007_universal/kod/p_355_ui_handlers.py"),
        ("UI Styles", "007_universal/kod/p_356_ui_styles.py"),
        ("UI Utils", "007_universal/kod/p_357_ui_utils.py"),
        ("AI Helper", "007_universal/kod/p_902_ai_helper.py"),
        ("Launcher", "007_universal/kod/p_996_gui_launcher.py"),
    ]
    
    navigation = manager.create_project_navigation(modules_list)
    print("Зразок RAG-навігації:")
    print("=" * 80)
    print(navigation)
    print("=" * 80)
    
    # Приклад 3: Генерація всіх URL
    print("\n\nУсі RAW URL проекту:")
    all_urls = manager.generate_all_urls()
    for filename, url in all_urls.items():
        print(f"{filename}: {url}")


if __name__ == "__main__":
    main()