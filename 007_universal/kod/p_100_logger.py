# p_100_logger.py
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Literal
from pydantic import BaseModel, Field

# --- КОНФІГУРАЦІЯ МОДУЛЯ ---
# p_100_logger.py (додати до існуючого коду)
DEFAULT_CONFIG = {
    'logging': {
        'level': 'INFO',
        'file': 'logs/app.log',
        'rotation_size_mb': 1
    }
}


class LoggingConfig(BaseModel):
    """Модель конфігурації для логування (визначена всередині модуля)"""
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    file: str = "logs/app.log"
    rotation_size_mb: int = Field(5, gt=0)

def prepare_config_models() -> Dict[str, Any]:
    """Повертає модель конфігурації для цього модуля."""
    return {'logging': LoggingConfig}

# --- ЛОГІКА МОДУЛЯ ---

# (Сумісний імпорт colorama залишаємо без змін)
try:
    import colorama  # type: ignore
    colorama.init()
except Exception:
    colorama = None  # type: ignore

class ColorFormatter(logging.Formatter):
    """Форматер з кольорами для консольного виводу."""
    ANSI_FALLBACK = {
        'DEBUG': '\033[94m', 'INFO': '\033[92m', 'WARNING': '\033[93m',
        'ERROR': '\033[91m', 'CRITICAL': '\033[95m', 'RESET': '\033[0m',
    }

    def __init__(self, fmt: str = None, datefmt: str = None) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        if colorama:
            fore = colorama.Fore
            style = colorama.Style
            self.colors = {
                'DEBUG': getattr(fore, 'BLUE', self.ANSI_FALLBACK['DEBUG']),
                'INFO': getattr(fore, 'GREEN', self.ANSI_FALLBACK['INFO']),
                'WARNING': getattr(fore, 'YELLOW', self.ANSI_FALLBACK['WARNING']),
                'ERROR': getattr(fore, 'RED', self.ANSI_FALLBACK['ERROR']),
                'CRITICAL': getattr(fore, 'MAGENTA', self.ANSI_FALLBACK['CRITICAL']),
                'RESET': getattr(style, 'RESET_ALL', self.ANSI_FALLBACK['RESET']),
            }
        else:
            self.colors = self.ANSI_FALLBACK

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        color = self.colors.get(record.levelname, '')
        reset = self.colors.get('RESET', '')
        return f"{color}{formatted}{reset}" if color else formatted

ROOT_LOGGER_NAME = "modular_project"

def _resolve_level(level: Any) -> int:
    if isinstance(level, int): return level
    if isinstance(level, str): return getattr(logging, level.upper(), logging.INFO)
    return logging.INFO

def initialize(app_context: Dict[str, Any]) -> logging.Logger:
    """Ініціалізація логера з використанням app_context."""
    config = app_context.get('config')
    
    # Тепер ми впевнені, що config має атрибут logging, бо ми передали модель вище
    if not hasattr(config, 'logging'):
        # Fallback на випадок помилки
        print("WARN: Config for logging missing, using defaults")
        log_conf = LoggingConfig() 
    else:
        log_conf = config.logging

    # Створення папки для логів, якщо немає
    log_dir = os.path.dirname(log_conf.file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    max_bytes = int(log_conf.rotation_size_mb) * 1024 * 1024
    file_handler = RotatingFileHandler(
        filename=log_conf.file, maxBytes=max_bytes, backupCount=5, encoding='utf-8'
    )
    
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    file_formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColorFormatter(fmt=log_format, datefmt=date_format))

    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(_resolve_level(log_conf.level))
    
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    logger.info("--- Система логування успішно ініціалізована ---")
    app_context['logger'] = logger
    return logger

def stop(app_context: Dict[str, Any]) -> None:
    """Закриття хендлерів при зупинці."""
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)