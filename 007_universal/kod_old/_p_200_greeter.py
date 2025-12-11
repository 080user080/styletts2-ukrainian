# Файл: kod/p_200_greeter.py (Оновлено: 2025-11-13 21:38 EET)
"""
Модуль P_200: Greeter
Демонстраційний модуль, який показує використання логера і конфігурації.
Тепер сам себе конфігурує, використовуючи prepare_config_models().
"""
from pydantic import BaseModel, Field
from typing import Dict, Any
import logging


# --- ЕТАП 1: ОГОЛОШЕННЯ КОНФІГУРАЦІЇ ---

class GreeterConfig(BaseModel):
    """Модель конфігурації для Greeter."""
    message: str = Field("Вітаю! Модульна система успішно працює.", description="Повідомлення для виводу.")
    repeat: int = Field(3, gt=0, description="Кількість повторів повідомлення.")


def initialize(app_context: Dict[str, Any]) -> None:
    """
    Ініціалізує логіку Greeter.
    """
    config = app_context['config']
    logger = app_context['logger']
    
    # Перевірка наявності конфігурації greeter з більш гнучкою обробкою
    if hasattr(config, 'greeter'):
        greeter_conf = config.greeter
    else:
        # Якщо конфігурації немає, використовуємо значення за замовчуванням
        greeter_conf = GreeterConfig()
        logger.warning("Greeter: конфігурація не знайдена. Використовуються значення за замовчуванням.")
        
    greeter_logger = logger.getChild('Greeter')
    greeter_logger.info("Підготовка Greeter...")

    greeter_logger.info(f"Запуск логіки. Повідомлення буде повторено {greeter_conf.repeat} разів.")
    
    for i in range(1, greeter_conf.repeat + 1):
        greeter_logger.info(f"({i}/{greeter_conf.repeat}) {greeter_conf.message}")

    greeter_logger.warning("Демонстраційна логіка завершена.")
    
    # Greeter не повертає об'єкт в контекст, але можемо повернути None або True
    return None