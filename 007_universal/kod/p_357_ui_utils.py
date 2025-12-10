# p_357_ui_utils.py
"""
Утиліти для розширеного UI Multi Dialog TTS.
Валідація вводу, створення папок сесій та допоміжні функції.
"""

import os
import re
import time
import logging
import tempfile
from typing import Dict, Any, Tuple, Optional, List, Union
from pathlib import Path
import numpy as np
import soundfile as sf

def validate_text_input(text: str, max_length: int = 50000) -> Tuple[bool, str]:
    """
    Валідація текстового вводу.
    
    Args:
        text: Текст для перевірки
        max_length: Максимальна довжина тексту
        
    Returns:
        (is_valid, error_message)
    """
    if not text or not isinstance(text, str):
        return False, "Текст не може бути порожнім"
    
    text = text.strip()
    
    if len(text) == 0:
        return False, "Текст не може бути порожнім"
    
    if len(text) > max_length:
        return False, f"Текст занадто довгий ({len(text)} символів). Максимум: {max_length}"
    
    # Перевірка на наявність корисного вмісту (не тільки пробіли/переноси)
    if not re.search(r'[а-яА-Яa-zA-Z0-9]', text):
        return False, "Текст має містити літери або цифри"
    
    return True, ""

def validate_file_input(file_path: str, allowed_extensions: List[str] = None) -> Tuple[bool, str, str]:
    """
    Валідація файлу вводу.
    
    Args:
        file_path: Шлях до файлу
        allowed_extensions: Дозволені розширення (за замовчуванням .txt)
        
    Returns:
        (is_valid, error_message, file_content)
    """
    if not file_path:
        return False, "Файл не вибрано", ""
    
    if allowed_extensions is None:
        allowed_extensions = ['.txt', '.text', '.md']
    
    # Перевірка існування файлу
    if not os.path.exists(file_path):
        return False, f"Файл не знайдено: {file_path}", ""
    
    # Перевірка розширення
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext not in allowed_extensions:
        ext_list = ', '.join(allowed_extensions)
        return False, f"Непідтримуване розширення файлу. Дозволені: {ext_list}", ""
    
    # Перевірка розміру файлу (максимум 5MB)
    try:
        file_size = os.path.getsize(file_path)
        if file_size > 5 * 1024 * 1024:  # 5MB
            return False, f"Файл занадто великий ({file_size // 1024}KB). Максимум: 5MB", ""
    except Exception:
        pass
    
    # Читання файлу
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Перевірка вмісту файлу
        if not content or len(content.strip()) == 0:
            return False, "Файл порожній", ""
        
        return True, "", content
        
    except UnicodeDecodeError:
        return False, "Файл має бути в кодуванні UTF-8", ""
    except Exception as e:
        return False, f"Помилка читання файлу: {str(e)}", ""

def create_session_directory(base_dir: str = "output_audio") -> Tuple[str, str]:
    """
    Створює унікальну директорію для сесії синтезу.
    
    Args:
        base_dir: Базова директорія для створення сесії
        
    Returns:
        (session_path, session_id)
    """
    try:
        # Створюємо базову директорію якщо не існує
        os.makedirs(base_dir, exist_ok=True)
        
        # Генеруємо унікальний ID сесії
        timestamp = int(time.time())
        session_id = f"session_{timestamp}_{os.getpid()}_{os.urandom(4).hex()[:8]}"
        
        # Створюємо шлях до сесії
        session_path = os.path.join(base_dir, session_id)
        os.makedirs(session_path, exist_ok=True)
        
        # Створюємо інформаційний файл сесії
        session_info = {
            'session_id': session_id,
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'base_dir': base_dir,
            'session_path': session_path,
        }
        
        info_file = os.path.join(session_path, '_session_info.json')
        import json
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(session_info, f, indent=2, ensure_ascii=False)
        
        return session_path, session_id
        
    except Exception as e:
        # Fallback до тимчасової директорії
        temp_dir = tempfile.mkdtemp(prefix='tts_session_')
        return temp_dir, f"temp_{os.path.basename(temp_dir)}"

def validate_voice_settings(voices: List[str], speeds: List[float]) -> Tuple[bool, str]:
    """
    Валідація налаштувань голосів та швидкостей.
    
    Args:
        voices: Список голосів (до 30)
        speeds: Список швидкостей (до 30)
        
    Returns:
        (is_valid, error_message)
    """
    if len(voices) > 30:
        return False, "Занадто багато голосів (максимум 30)"
    
    if len(speeds) > 30:
        return False, "Занадто багато швидкостей (максимум 30)"
    
    # Перевірка швидкостей
    for i, speed in enumerate(speeds):
        try:
            speed_val = float(speed)
            if not 0.5 <= speed_val <= 2.0:
                return False, f"Швидкість #{i+1} має бути від 0.5 до 2.0 (отримано {speed_val})"
        except (ValueError, TypeError):
            return False, f"Невірне значення швидкості #{i+1}: {speed}"
    
    return True, ""

def parse_script_and_validate(text: str, dialog_parser: Any) -> Tuple[bool, str, List[Dict]]:
    """
    Парсить сценарій та валідує його структуру.
    
    Args:
        text: Текст сценарію
        dialog_parser: Об'єкт DialogParser для парсингу
        
    Returns:
        (is_valid, error_message, parsed_events)
    """
    try:
        # Парсинг сценарію (використовуємо пустий список голосів для валідації)
        events = dialog_parser.parse_script_events(text, [])
        
        if not events:
            return False, "Сценарій не містить дій", []
        
        # Перевірка наявності невідомих тегів
        for event in events:
            if event.get('type') not in ['voice', 'sfx']:
                return False, f"Невідомий тип події: {event.get('type')}", []
            
            if event.get('type') == 'voice' and event.get('g', 0) > 30:
                return False, f"Номер спікера #{event.get('g')} перевищує 30", []
        
        return True, "", events
        
    except Exception as e:
        return False, f"Помилка парсингу сценарію: {str(e)}", []

def save_audio_part(audio: np.ndarray, sample_rate: int, part_index: int, 
                   output_dir: str, prefix: str = "part") -> Optional[str]:
    """
    Безпечно зберігає частину аудіо.
    
    Args:
        audio: Аудіо дані
        sample_rate: Частота дискретизації
        part_index: Номер частини
        output_dir: Директорія для збереження
        prefix: Префікс імені файлу
        
    Returns:
        Шлях до збереженого файлу або None
    """
    try:
        # Перевірка та створення директорії
        os.makedirs(output_dir, exist_ok=True)
        
        # Генерація імені файлу
        filename = f"{prefix}_{part_index:03d}.wav"
        filepath = os.path.join(output_dir, filename)
        
        # Перевірка, чи аудіо у правильному форматі
        if isinstance(audio, np.ndarray):
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
        else:
            audio = np.array(audio, dtype=np.float32)
        
        # Запис аудіо
        sf.write(filepath, audio, sample_rate)
        
        return filepath
        
    except Exception as e:
        # Fallback до тимчасової директорії
        try:
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
                sf.write(tmp_path, audio, sample_rate)
                return tmp_path
        except Exception:
            return None

def calculate_time_estimate(processed_parts: int, total_parts: int, 
                           start_time: float) -> Dict[str, str]:
    """
    Розраховує оцінку часу виконання.
    
    Args:
        processed_parts: Оброблено частин
        total_parts: Всього частин
        start_time: Час початку
        
    Returns:
        Словник з інформацією про час
    """
    current_time = time.time()
    elapsed = current_time - start_time
    
    result = {
        'elapsed': format_time(elapsed),
        'start_time': time.strftime('%H:%M:%S', time.localtime(start_time)),
        'current_time': time.strftime('%H:%M:%S', time.localtime(current_time)),
        'estimated_finish': None,
        'remaining': None,
    }
    
    if processed_parts > 0:
        # Середній час на частину
        avg_time_per_part = elapsed / processed_parts
        
        # Загальний очікуваний час
        estimated_total = avg_time_per_part * total_parts
        
        # Очікуваний час завершення
        estimated_finish_time = start_time + estimated_total
        result['estimated_finish'] = time.strftime('%H:%M:%S', time.localtime(estimated_finish_time))
        
        # Залишилось часу
        remaining_seconds = estimated_finish_time - current_time
        if remaining_seconds > 0:
            result['remaining'] = format_time(remaining_seconds)
    
    return result

def format_time(seconds: float) -> str:
    """
    Форматує час у зручний для читання вигляд.
    
    Args:
        seconds: Кількість секунд
        
    Returns:
        Рядок у форматі "X хв Y сек" або "Z год X хв"
    """
    seconds = int(seconds)
    
    if seconds < 60:
        return f"{seconds} сек"
    
    minutes = seconds // 60
    seconds_remain = seconds % 60
    
    if minutes < 60:
        if seconds_remain > 0:
            return f"{minutes} хв {seconds_remain} сек"
        else:
            return f"{minutes} хв"
    
    hours = minutes // 60
    minutes_remain = minutes % 60
    
    if minutes_remain > 0:
        return f"{hours} год {minutes_remain} хв"
    else:
        return f"{hours} год"

def create_progress_update(current: int, total: int, message: str = "") -> Dict[str, Any]:
    """
    Створює об'єкт оновлення прогресу.
    
    Args:
        current: Поточне значення
        total: Загальне значення
        message: Додаткове повідомлення
        
    Returns:
        Словник з даними для оновлення UI
    """
    percentage = (current / total * 100) if total > 0 else 0
    
    return {
        'current': current,
        'total': total,
        'percentage': percentage,
        'message': message,
        'timestamp': time.time(),
        'formatted': f"{current}/{total} ({percentage:.1f}%)",
    }

def validate_sfx_id(sfx_id: str, sfx_handler: Any) -> Tuple[bool, str]:
    """
    Валідує ID звукового ефекту.
    
    Args:
        sfx_id: ID SFX для перевірки
        sfx_handler: Об'єкт SFXHandler
        
    Returns:
        (is_valid, error_message)
    """
    if not sfx_id or not isinstance(sfx_id, str):
        return False, "SFX ID не може бути порожнім"
    
    # Перевірка формату ID (букви, цифри, підкреслення)
    if not re.match(r'^[a-zA-Z0-9_]+$', sfx_id):
        return False, f"Невірний формат SFX ID: {sfx_id}. Дозволені лише букви, цифри та підкреслення"
    
    # Перевірка наявності в конфігурації
    if sfx_handler and not sfx_handler.validate_sfx_id(sfx_id):
        available_sfx = sfx_handler.get_available_sfx_ids()
        available_list = ', '.join(available_sfx[:5])
        if len(available_sfx) > 5:
            available_list += f" та ще {len(available_sfx) - 5}..."
        
        return False, f"SFX '{sfx_id}' не знайдено. Доступні: {available_list}"
    
    return True, ""

def cleanup_old_sessions(base_dir: str = "output_audio", 
                        max_age_hours: int = 24,
                        max_sessions: int = 50) -> List[str]:
    """
    Очищує старі сесії для економії місця.
    
    Args:
        base_dir: Базова директорія сесій
        max_age_hours: Максимальний вік сесії в годинах
        max_sessions: Максимальна кількість сесій для збереження
        
    Returns:
        Список видалених сесій
    """
    if not os.path.exists(base_dir):
        return []
    
    deleted = []
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    try:
        # Отримуємо всі сесії
        sessions = []
        for item in os.listdir(base_dir):
            session_path = os.path.join(base_dir, item)
            if os.path.isdir(session_path) and item.startswith('session_'):
                sessions.append({
                    'path': session_path,
                    'name': item,
                    'created': os.path.getctime(session_path)
                })
        
        # Сортуємо за датою створення (новіші спочатку)
        sessions.sort(key=lambda x: x['created'], reverse=True)
        
        # Видаляємо занадто старі сесії
        for session in sessions:
            age = current_time - session['created']
            if age > max_age_seconds:
                try:
                    import shutil
                    shutil.rmtree(session['path'])
                    deleted.append(session['name'])
                except Exception:
                    pass
        
        # Обмежуємо кількість сесій
        if len(sessions) > max_sessions:
            for session in sessions[max_sessions:]:
                try:
                    import shutil
                    shutil.rmtree(session['path'])
                    if session['name'] not in deleted:
                        deleted.append(session['name'])
                except Exception:
                    pass
        
        return deleted
        
    except Exception as e:
        return []

def get_system_info() -> Dict[str, Any]:
    """
    Повертає інформацію про систему для логування.
    
    Returns:
        Словник з інформацією про систему
    """
    import platform
    import sys
    
    return {
        'platform': platform.system(),
        'platform_version': platform.version(),
        'python_version': platform.python_version(),
        'cpu_count': os.cpu_count(),
        'current_directory': os.getcwd(),
        'free_disk_space': get_free_disk_space(),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

def get_free_disk_space(path: str = ".") -> Optional[str]:
    """
    Повертає вільне місце на диску.
    
    Args:
        path: Шлях для перевірки
        
    Returns:
        Рядок з вільною пам'яттю у зручному форматі
    """
    try:
        import shutil
        stat = shutil.disk_usage(path)
        free_gb = stat.free / (1024**3)
        
        if free_gb >= 1:
            return f"{free_gb:.1f} GB"
        else:
            free_mb = stat.free / (1024**2)
            return f"{free_mb:.0f} MB"
    except Exception:
        return None

# Константи для використання в інших модулях
DEFAULT_SETTINGS = {
    'max_text_length': 50000,
    'max_file_size_mb': 5,
    'max_speakers': 30,
    'min_speed': 0.5,
    'max_speed': 2.0,
    'default_speed': 0.88,
    'session_cleanup_hours': 24,
    'max_sessions': 50,
}

VALID_FILE_EXTENSIONS = ['.txt', '.text', '.md', '.json', '.yaml', '.yml']