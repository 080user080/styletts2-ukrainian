# p_013_report_cleaner.py
"""
Модуль для очищення застарілих звітів конфігурації та проекту.
Зберігає максимум 2 файли в config_reports/ та 4 файли в project_info/
Остаток видаляються під час ініціалізації.
"""

import os
import glob
from pathlib import Path
from typing import Dict, Any, List
import logging
from datetime import datetime

class ReportCleaner:
    """Очищувач застарілих звітів."""
    
    # Конфігурація
    CONFIG_REPORTS_DIR = "config_reports"
    PROJECT_INFO_DIR = "project_info"
    CONFIG_MAX_FILES = 2
    PROJECT_MAX_FILES = 4
    
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.logger = logging.getLogger("ReportCleaner")
        self.project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))).parent
        
    def _get_yaml_files(self, directory: str) -> List[tuple]:
        """
        Отримує список .yaml/.txt файлів з цвіслов(дата_файлу, шлях)
        Сортовані від найновіших до найстаріших.
        """
        dir_path = self.project_root / directory
        
        if not dir_path.exists():
            return []
        
        files = []
        
        # Шукаємо .yaml та .txt файли
        for pattern in ['*.yaml', '*.yml', '*.txt']:
            for filepath in dir_path.glob(pattern):
                if filepath.is_file():
                    # Отримуємо час модифікації
                    mtime = filepath.stat().st_mtime
                    files.append((mtime, str(filepath)))
        
        # Сортуємо за часом (найновіші спочатку)
        files.sort(reverse=True)
        
        return files
    
    def _delete_old_files(self, directory: str, max_keep: int) -> int:
        """
        Видаляє старі файли, зберігаючи тільки max_keep останніх.
        
        Returns:
            Кількість видалених файлів
        """
        dir_path = self.project_root / directory
        
        if not dir_path.exists():
            return 0
        
        files = self._get_yaml_files(directory)
        
        if len(files) <= max_keep:
            return 0
        
        deleted_count = 0
        
        # Видаляємо всі файли крім останніх max_keep
        for mtime, filepath in files[max_keep:]:
            try:
                file_name = Path(filepath).name
                os.remove(filepath)
                self.logger.info(f"🗑️  Видалено: {directory}/{file_name}")
                deleted_count += 1
            except Exception as e:
                self.logger.warning(f"⚠️  Не вдалося видалити {filepath}: {e}")
        
        return deleted_count
    
    def cleanup(self) -> Dict[str, int]:
        """
        Виконує очищення обох папок.
        
        Returns:
            {'config_reports': кількість_видалених, 'project_info': кількість_видалених}
        """
        result = {
            'config_reports': 0,
            'project_info': 0
        }
        
        # Очищуємо config_reports (максимум 2 файли)
        self.logger.info(f"🧹 Очищення {self.CONFIG_REPORTS_DIR}/ (макс. {self.CONFIG_MAX_FILES} файлів)...")
        result['config_reports'] = self._delete_old_files(
            self.CONFIG_REPORTS_DIR,
            self.CONFIG_MAX_FILES
        )
        
        if result['config_reports'] > 0:
            self.logger.info(f"✅ Видалено {result['config_reports']} старих файлів з {self.CONFIG_REPORTS_DIR}/")
        
        # Очищуємо project_info (максимум 4 файли)
        self.logger.info(f"🧹 Очищення {self.PROJECT_INFO_DIR}/ (макс. {self.PROJECT_MAX_FILES} файлів)...")
        result['project_info'] = self._delete_old_files(
            self.PROJECT_INFO_DIR,
            self.PROJECT_MAX_FILES
        )
        
        if result['project_info'] > 0:
            self.logger.info(f"✅ Видалено {result['project_info']} старих файлів з {self.PROJECT_INFO_DIR}/")
        
        # Загальний результат
        total_deleted = result['config_reports'] + result['project_info']
        if total_deleted > 0:
            self.logger.info(f"✅ Всього очищено: {total_deleted} файлів")
        else:
            self.logger.info("✅ Очищення не потрібне (всі файли свіжі)")
        
        return result
    
    def show_status(self) -> Dict[str, Any]:
        """Показує статус файлів в папках."""
        status = {
            'config_reports': {
                'max_files': self.CONFIG_MAX_FILES,
                'current_files': [],
                'excess_files': 0
            },
            'project_info': {
                'max_files': self.PROJECT_MAX_FILES,
                'current_files': [],
                'excess_files': 0
            }
        }
        
        for directory, config in [
            (self.CONFIG_REPORTS_DIR, status['config_reports']),
            (self.PROJECT_INFO_DIR, status['project_info'])
        ]:
            files = self._get_yaml_files(directory)
            config['current_files'] = [Path(f[1]).name for f in files]
            config['excess_files'] = max(0, len(files) - config['max_files'])
        
        return status


def prepare_config_models():
    """Конфігурація не потрібна."""
    return {}


def initialize(app_context: Dict[str, Any]) -> ReportCleaner:
    """Ініціалізація очищувача звітів."""
    logger = app_context.get('logger', logging.getLogger("ReportCleaner"))
    logger.info("🧹 Ініціалізація модуля очищення звітів...")
    
    cleaner = ReportCleaner(app_context)
    
    # Виконуємо очищення
    result = cleaner.cleanup()
    
    # Додаємо в контекст для можливості повторного використання
    app_context['report_cleaner'] = {
        'cleanup': cleaner.cleanup,
        'show_status': cleaner.show_status,
        'instance': cleaner
    }
    
    logger.info("✅ Модуль очищення звітів готовий")
    
    return cleaner


def stop(app_context: Dict[str, Any]) -> None:
    """Зупинка модуля."""
    if 'report_cleaner' in app_context:
        del app_context['report_cleaner']
    
    logger = app_context.get('logger')
    if logger:
        logger.info("Модуль очищення звітів зупинено")
