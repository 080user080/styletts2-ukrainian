"""
a_4_progress_logic.py
Логіка прогресу: обчислення часу, прогноз завершення.
"""

import time
from a_7_utils import format_hms


def estimate_remaining(
    current_idx: int,
    total_parts: int,
    times_per_part: list,
    global_start: float
) -> tuple[str, str]:
    """
    Обчислює прогноз часу завершення й залишок часу.
    
    Returns:
      (est_finish_str, remaining_str)  -- час завершення HH:MM:SS і текст до закінчення
    """
    now = time.time()
    
    if not times_per_part:
        return ("Розрахунок...", "Розрахунок...")
    
    avg_time = sum(times_per_part) / len(times_per_part)
    est_total_time = avg_time * total_parts
    est_finish = time.localtime(global_start + est_total_time)
    est_finish_str = time.strftime('%H:%M:%S', est_finish)
    
    rem_secs = int(global_start + est_total_time - now)
    rem_secs = max(rem_secs, 0)
    rem_min, rem_sec = divmod(rem_secs, 60)
    rem_text = f"до закінчення залишилося {rem_min} хв {rem_sec} сек"
    
    return (est_finish_str, rem_text)


def get_elapsed_str(global_start: float) -> str:
    """Повертає рядок часу з моменту старту."""
    elapsed = int(time.time() - global_start)
    return f"{elapsed} сек --- {format_hms(elapsed)}"
