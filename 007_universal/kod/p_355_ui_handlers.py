# p_355_ui_handlers.py
"""
Обробники подій для розширеного UI Multi Dialog TTS.
Основні функції для синтезу, експорту та обробки прикладів.
"""

import os
import time
import logging
import traceback
from typing import Dict, Any, List, Callable
import numpy as np
import soundfile as sf
import tempfile

def create_batch_synthesize_handler(app_context: Dict[str, Any], output_dir: str) -> Callable:
    """
    Створює обробник для пакетного синтезу.
    
    Args:
        app_context: Контекст додатку з компонентами
        output_dir: Директорія для збереження результатів
        
    Returns:
        Функція-обробник для batch_synthesize_events
    """
    logger = app_context.get('logger', logging.getLogger("UI_Handlers"))
    
    def batch_synthesize_events(*args):
        """
        Основна функція обробки пакетного синтезу.
        Обробляє всі події сценарію та генерує аудіо.
        
        ✅ ОСТАТОЧНА ВЕРСІЯ: Правильна обробка аудіо та файлів
        """
        
        try:
            # Розпакування аргументів
            text_input = args[0]
            file_input = args[1]
            speeds_flat = list(args[2:32])      # 30 швидкостей
            voices_flat = list(args[32:62])     # 30 голосів
            save_option = args[62] if len(args) > 62 else "Без збереження"
            ignore_speed = bool(args[63]) if len(args) > 63 else False
            
            logger.info(f"Отримано {len(args)} аргументів: speeds={len(speeds_flat)}, voices={len(voices_flat)}")
            
            # Отримання компонентів
            tts_engine = app_context.get('tts_engine')
            dialog_parser = app_context.get('dialog_parser')
            sfx_handler = app_context.get('sfx_handler')
            
            if not all([tts_engine, dialog_parser, sfx_handler]):
                raise RuntimeError("Відсутні компоненти TTS для синтезу")
            
            # Читання тексту
            if text_input and text_input.strip():
                text = text_input
            elif file_input:
                with open(file_input, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                raise ValueError("Введіть текст або виберіть файл")
            
            # Парсинг подій
            events = dialog_parser.parse_script_events(text, voices_flat)
            total_parts = len(events)
            
            logger.info(f"Парсено {total_parts} подій для синтезу")
            
            start_time = time.time()
            times_per_part = []
            voice_map = {i+1: voices_flat[i] if i < len(voices_flat) else None 
                        for i in range(30)}
            
            # Початковий update для прогресу
            yield (
                None,  # audio_output
                1,     # part_slider value
                f"1/{total_parts}",  # part_slider maximum
                "0 сек",
                time.strftime('%H:%M:%S', time.localtime(start_time)),
                "",
                "Розрахунок...",
                "Розрахунок...",
                0,     # progress_slider value
                total_parts  # progress_slider maximum
            )
            
            # Обробка кожної події
            for idx, event in enumerate(events, start=1):
                part_start = time.time()
                
                try:
                    if event.get('type') == 'voice':
                        g_num = event.get('g')
                        text_body = event.get('text', '')
                        suffix = event.get('suffix', '')
                        voice_name = voice_map.get(g_num, None)
                        speed = dialog_parser.compute_speed_effective(
                            g_num, suffix, speeds_flat, ignore_speed
                        )
                        
                        # Синтез через TTS engine
                        result = tts_engine.synthesize(
                            text=text_body,
                            speaker_id=g_num,
                            speed=speed,
                            voice=voice_name
                        )
                        
                        audio = result['audio']
                        sr = result['sample_rate']
                        
                        # Переконатися що аудіо у правильному форматі
                        if isinstance(audio, np.ndarray):
                            if audio.dtype != np.float32:
                                audio = audio.astype(np.float32)
                        else:
                            audio = np.array(audio, dtype=np.float32)
                        
                    elif event.get('type') == 'sfx':
                        sfx_id = event.get('id')
                        
                        # Завантажити SFX
                        sr, audio = sfx_handler.load_and_process_sfx(sfx_id)
                        
                        # Переконатися що аудіо у правильному форматі
                        if isinstance(audio, np.ndarray):
                            if audio.dtype != np.float32:
                                audio = audio.astype(np.float32)
                        else:
                            audio = np.array(audio, dtype=np.float32)
                        
                    else:
                        logger.warning(f"Невідомий тип події: {event}")
                        continue
                    
                    # Безпечне збереження файлу
                    part_path = os.path.join(output_dir, f"part_{idx:03d}.wav")
                    
                    try:
                        sf.write(part_path, audio, sr)
                        logger.info(f"✅ Частина {idx} збережена: {part_path}")
                    except Exception as write_error:
                        logger.error(f"Помилка збереження файлу {part_path}: {write_error}")
                        # Fallback: тимчасова папка
                        with tempfile.TemporaryDirectory() as tmpdir:
                            part_path = os.path.join(tmpdir, f"part_{idx:03d}.wav")
                            sf.write(part_path, audio, sr)
                            logger.info(f"✅ Частина {idx} збережена у temp: {part_path}")
                    
                    # Обновлення таймінгу
                    part_end = time.time()
                    elapsed = int(part_end - start_time)
                    times_per_part.append(part_end - part_start)
                    
                    # Прогноз часу
                    if times_per_part:
                        avg_time = sum(times_per_part) / len(times_per_part)
                        est_total = avg_time * total_parts
                        est_finish = time.strftime('%H:%M:%S', time.localtime(start_time + est_total))
                        remaining_secs = int(start_time + est_total - part_end)
                        rem_min, rem_sec = divmod(max(remaining_secs, 0), 60)
                        remaining_text = f"{rem_min} хв {rem_sec} сек"
                    else:
                        est_finish = "Розрахунок..."
                        remaining_text = "Розрахунок..."
                    
                    # Yield обновлення
                    yield (
                        part_path if os.path.exists(part_path) else None,  # audio_output
                        idx,  # part_slider value
                        f"{idx}/{total_parts}",  # part_slider label
                        f"{elapsed} сек",
                        time.strftime('%H:%M:%S', time.localtime(start_time)),
                        time.strftime('%H:%M:%S', time.localtime(part_end)),
                        est_finish,
                        remaining_text,
                        idx,  # progress_slider value
                        total_parts  # progress_slider maximum
                    )
                    
                except Exception as e:
                    logger.error(f"Помилка обробки частини {idx}: {e}")
                    traceback.print_exc()
                    raise
            
            # Завершення
            total_elapsed = int(time.time() - start_time)
            logger.info(f"✅ Синтез завершено за {total_elapsed} сек")
            
            yield (
                None,
                total_parts,
                f"{total_parts}/{total_parts}",
                f"Завершено за {total_elapsed} сек",
                time.strftime('%H:%M:%S', time.localtime(start_time)),
                time.strftime('%H:%M:%S', time.localtime(time.time())),
                "Завершено",
                "",
                total_parts,
                total_parts
            )
        
        except Exception as e:
            logger.error(f"Критична помилка: {e}")
            traceback.print_exc()
            raise
    
    return batch_synthesize_events

def create_export_settings_handler(app_context: Dict[str, Any], output_dir: str) -> Callable:
    """
    Створює обробник для експорту налаштувань.
    
    Args:
        app_context: Контекст додатку
        output_dir: Директорія для збереження
        
    Returns:
        Функція-обробник для export_settings
    """
    logger = app_context.get('logger', logging.getLogger("UI_Handlers"))
    
    def export_settings(*values):
        """Експорт налаштувань спікерів у текстовий файл."""
        voices = list(values[:30])
        speeds = list(values[30:60])
        
        import time
        filename = f"settings_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = os.path.join(output_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("# Налаштування спікерів TTS Multi Dialog\n")
                f.write(f"# Згенеровано: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("# Формат: #gN: голос (швидкість: X.XX)\n\n")
                
                for i in range(30):
                    voice = str(voices[i]).strip() if i < len(voices) else "default"
                    speed = float(speeds[i]) if i < len(speeds) else 0.88
                    f.write(f"#g{i+1}: {voice} (швидкість: {speed:.2f})\n")
            
            logger.info(f"✅ Налаштування експортовані: {filepath}")
            
            # Повертаємо шлях до файлу для завантаження
            return f"file://{os.path.abspath(filepath)}"
            
        except Exception as e:
            logger.error(f"Помилка експорту: {e}")
            return f"Помилка: {str(e)}"
    
    return export_settings

def create_example_handler() -> Callable:
    """
    Створює обробник для вибору прикладів.
    
    Returns:
        Функція-обробник для select_example
    """
    def select_example(example_data):
        """
        Обробляє вибір прикладу з таблиці.
        
        Args:
            example_data: Дані з вибраного рядка таблиці
            
        Returns:
            Текст прикладу та значення швидкості
        """
        try:
            if isinstance(example_data, dict) and 'data' in example_data:
                # Градіо передає дані як об'єкт
                selected_row = example_data['data']
                if selected_row and len(selected_row) >= 2:
                    return selected_row[0], float(selected_row[1])
            elif isinstance(example_data, (list, tuple)) and len(example_data) >= 2:
                # Прямий виклик
                return example_data[0], float(example_data[1])
        except Exception as e:
            print(f"Помилка обробки прикладу: {e}")
        
        return "", 0.9
    
    return select_example

# Стандартні приклади для інтерфейсу
def get_default_examples() -> List[List]:
    """
    Повертає список прикладів для UI.
    
    Returns:
        Список прикладів у форматі [[текст, швидкість], ...]
    """
    return [
        ["Одна дівчинка стала королевою Франції. Звали її Анна, і була вона донькою Ярослава Му+дрого, великого київського князя.", 0.88],
        ["#g1: Привіт! Як справи?\n#g2: Все добре, дякую! А ти як?\n#g1: Теж добре, радий тебе бачити!", 0.9],
        ["#g1_fast: Швидка репліка!\n#g2_slow: Повільна відповідь.\n#g1: Звичайна швидкість.", 1.0],
        ["#g1: Перша репліка.\n#bell\n#g2: Друга репліка після дзвіночка.", 0.85],
        ["Довгий текст для тестування розбиття на частини. " * 20, 0.88]
    ]