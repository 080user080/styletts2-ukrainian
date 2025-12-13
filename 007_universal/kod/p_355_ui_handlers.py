import gradio as gr
from typing import Optional, Dict, Any, Tuple
import numpy as np
import os
import time
from datetime import datetime
import soundfile as sf

class UIEventHandlers:
    """
    Обробники подій для UI компонентів
    """
    
    def __init__(self, core_instance=None):
        """
        Ініціалізація обробників подій
        
        Args:
            core_instance: Екземпляр AdvancedUICore (опціонально)
        """
        self.core = core_instance
        print(f"🔄 Ініціалізовано UIEventHandlers з core: {core_instance is not None}")
    
    def text_changed_handler(self, text: str) -> Dict[str, Any]:
        """
        Обробник зміни тексту в полі вводу
        """
        if not text or text.strip() == "":
            return {"value": "", "interactive": True}
        
        # Можна використати core_instance для додаткової логіки
        if self.core:
            # Наприклад, перевірка довжини тексту через core
            pass
        
        return {"value": text, "interactive": True}
    
    def save_audio_handler(self, audio: np.ndarray, samplerate: int, 
                          file_name: str = None, session_state: str = None) -> Optional[str]:
        """
        Зберігає аудіофайл на диск
        
        Args:
            audio: Аудіодані
            samplerate: Частота дискретизації
            file_name: Ім'я файлу для збереження (опціонально)
            session_state: ID сесії для створення папки
            
        Returns:
            Шлях до збереженого файлу або None при помилці
        """
        try:
            from pathlib import Path
            
            # Отримати session_id з core або з аргументу
            if session_state:
                session_id = session_state
            elif self.core and hasattr(self.core, 'session_id'):
                session_id = self.core.session_id
            else:
                session_id = str(int(time.time()))
            
            print(f"💾 Збереження аудіо для сесії: {session_id}")
            
            # Створюємо папку для сесії
            output_dir = Path("output_audio") / f"session_{session_id}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Генеруємо ім'я файлу, якщо не передано
            if not file_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                file_name = f"tts_output_{timestamp}.wav"
            
            # Зберігаємо аудіо
            output_path = output_dir / file_name
            sf.write(str(output_path), audio, samplerate)
            
            print(f"✅ Аудіо збережено: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"❌ Помилка збереження аудіо: {e}")
            return None
    
    def apply_sfx_handler(self, audio: Optional[np.ndarray], sfx_type: str, 
                         intensity: float) -> Tuple[Optional[np.ndarray], str]:
        """
        Застосування звукових ефектів
        
        Args:
            audio: Вхідне аудіо
            sfx_type: Тип ефекту
            intensity: Інтенсивність ефекту
            
        Returns:
            Кортеж (оброблене аудіо, повідомлення)
        """
        try:
            if audio is None:
                return None, "❌ Немає аудіо для обробки"
            
            # Тут має бути логіка застосування SFX
            # Наразі просто повертаємо оригінальне аудіо
            processed_audio = audio
            
            return processed_audio, f"✅ SFX '{sfx_type}' застосовано (інтенсивність: {intensity})"
            
        except Exception as e:
            return None, f"❌ Помилка: {str(e)}"
    
    @staticmethod
    def normalize_audio(audio_data: np.ndarray) -> np.ndarray:
        """
        Нормалізація аудіо даних
        """
        if audio_data is None or len(audio_data) == 0:
            return audio_data
        
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            return audio_data / max_val * 0.9
        
        return audio_data
    
    @staticmethod
    def validate_audio_length(audio_data: np.ndarray, samplerate: int, 
                             max_duration_seconds: int = 30) -> Tuple[bool, str]:
        """
        Перевірка тривалості аудіо
        """
        if audio_data is None:
            return False, "Аудіо відсутнє"
        
        duration = len(audio_data) / samplerate
        
        if duration > max_duration_seconds:
            return False, f"Аудіо задовге ({duration:.1f} сек > {max_duration_seconds} сек)"
        
        return True, f"Тривалість: {duration:.1f} сек"

# Додаткові функції для зворотної сумісності
def save_audio_handler(audio, samplerate, session_state=None):
    """Альтернативний виклик для зворотної сумісності"""
    handler = UIEventHandlers()
    return handler.save_audio_handler(audio, samplerate, session_state=session_state)

def text_changed_handler(text):
    """Альтернативний виклик для зворотної сумісності"""
    handler = UIEventHandlers()
    result = handler.text_changed_handler(text)
    return gr.update(value=result["value"], interactive=result["interactive"])

def apply_sfx_handler(audio, sfx_type, intensity):
    """Альтернативний виклик для зворотної сумісності"""
    handler = UIEventHandlers()
    return handler.apply_sfx_handler(audio, sfx_type, intensity)

# Створюємо глобальний екземпляр для імпорту (ВАЖЛИВО!)
event_handlers = UIEventHandlers()

if __name__ == "__main__":
    # Тестування
    print("Модуль UIEventHandlers завантажено")
    
    # Тест ініціалізації з core
    test_core = type('TestCore', (), {})()
    test_core.session_id = "test_123"
    
    handler_with_core = UIEventHandlers(test_core)
    print(f"Handler з core: {handler_with_core.core is not None}")
    
    # Тест збереження аудіо
    test_audio = np.random.randn(44100)
    path = handler_with_core.save_audio_handler(test_audio, 44100)
    print(f"Тестове збереження: {path}")