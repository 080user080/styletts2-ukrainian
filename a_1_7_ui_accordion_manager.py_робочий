"""
a_1_7_ui_accordion_manager.py
Керування видимістю акордеонів на основі максимального номера спікера.
"""

import re
import os


def find_max_speaker_tag(text: str | None) -> int:
    """
    Шукає найбільший номер спікера #gN у тексті.
    
    Returns:
        int: максимальний номер спікера (1-30), або 0 якщо не знайдено
    
    Приклад:
        "#g1 текст\n#g4 текст\n#g2 текст" → 4
    """
    if not text:
        return 0
    
    # Шукаємо всі теги #gN (з опціональними суфіксами _slow, _fast тощо)
    pattern = re.compile(r'#g\s*([1-9]|[12]\d|30)', re.IGNORECASE)
    matches = [int(x) for x in pattern.findall(text)]
    
    if not matches:
        return 0
    
    return max(matches)


def get_accordion_visibility(max_speaker: int) -> dict:
    """
    Повертає словник видимості акордеонів на основі максимального спікера.
    
    Діапазони:
      - acc_1_3:   g1-g3    → видимий якщо max_speaker >= 1
      - acc_4_12:  g4-g12   → видимий якщо max_speaker >= 4
      - acc_more:  батько   → видимий якщо max_speaker >= 13 (тому що всередині g13+)
      - acc_13_21: g13-g21  → видимий якщо max_speaker >= 13
      - acc_22_30: g22-g30  → видимий якщо max_speaker >= 22
    
    Parameters:
        max_speaker: максимальний номер спікера (1-30)
    
    Returns:
        dict: {"acc_name": visible_bool, ...}
    
    Приклад:
        max_speaker=14 →
        {
            "acc_1_3": True,      # g1-g3 існує
            "acc_4_12": True,     # g4-g12 існує
            "acc_more": True,     # батько видимий, тому що всередині g13+
            "acc_13_21": True,    # g13-g21 існує, бо max=14
            "acc_22_30": False,
        }
    """
    return {
        "acc_1_3": max_speaker >= 1,
        "acc_4_12": max_speaker >= 4,
        "acc_more": max_speaker >= 13,      # Батько для додаткових — видимий якщо є g13+
        "acc_13_21": max_speaker >= 13,    # Вложений акордеон
        "acc_22_30": max_speaker >= 22,
    }


def read_text_from_file(file_path: str) -> str:
    """
    Читає текст з файлу.
    
    Parameters:
        file_path: шлях до файлу
    
    Returns:
        str: вміст файлу або ""
    """
    if not file_path or not os.path.exists(file_path):
        return ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return ""


def get_max_speaker_from_input(text_input: str | None, file_input: str | None) -> int:
    """
    Визначає максимальний номер спікера з поля тексту або файлу.
    Пріоритет: текстове поле > файл
    
    Parameters:
        text_input: текст з поля (може бути None)
        file_input: шлях до файлу (може бути None)
    
    Returns:
        int: максимальний номер спікера
    """
    # Спочатку перевіримо текстове поле
    if text_input and text_input.strip():
        max_speaker = find_max_speaker_tag(text_input)
        if max_speaker > 0:
            return max_speaker
    
    # Потім перевіримо файл
    if file_input:
        file_text = read_text_from_file(file_input)
        max_speaker = find_max_speaker_tag(file_text)
        if max_speaker > 0:
            return max_speaker
    
    return 0
