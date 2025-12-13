import gradio as gr
from typing import Optional, Dict, Any
import os
import sys

# Додаємо шлях до поточного каталогу для імпорту модулів
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from p_355_ui_handlers import UIEventHandlers
    from p_356_ui_styles import UIStyles
    from p_357_ui_utils import UIUtils
except ImportError as e:
    print(f"⚠️  Помилка імпорту UI компонентів: {e}")
    UIEventHandlers = None
    UIStyles = None
    UIUtils = None

class AdvancedUIBuilder:
    """
    Будівельник розширеного інтерфейсу для TTS системи
    """
    
    def __init__(self, core_instance=None, config=None, tts_engine=None):
        """
        Ініціалізація будівельника
        
        Args:
            core_instance: Екземпляр AdvancedUICore
            config: Конфігурація UI
            tts_engine: Екземпляр TTS рушія
        """
        self.core = core_instance
        self.config = config or {}
        self.tts_engine = tts_engine
        
        # Ініціалізація обробників подій - передаємо ТІЛЬКИ core_instance
        self.handlers = UIEventHandlers(
            core_instance=self.core
            # НЕ передаємо tts_engine - це викликало помилку!
        ) if UIEventHandlers else None
        
        # Ініціалізація стилів
        self.styles = UIStyles() if UIStyles else None
        
        # Ініціалізація утиліт
        self.utils = UIUtils() if UIUtils else None
        
        print(f"🔄 AdvancedUIBuilder ініціалізовано. TTS Engine доступний: {self.tts_engine is not None}")
        
    def create_advanced_ui(self, core_instance=None) -> Optional[gr.Blocks]:
        """
        Створює розширений інтерфейс
        
        Args:
            core_instance: Екземпляр AdvancedUICore
            
        Returns:
            Інтерфейс Gradio або None при помилці
        """
        try:
            if core_instance:
                self.core = core_instance
            
            if not self.core:
                print("❌ Не вказано core_instance для створення UI")
                return None
            
            # Використовуємо стилі з core або стандартні
            css = self.core.css if hasattr(self.core, 'css') else ""
            
            # Створюємо заголовок з ID сесії
            session_id = self.core.session_id if hasattr(self.core, 'session_id') else "unknown"
            
            with gr.Blocks(title=f"Advanced TTS UI | Session: {session_id}", css=css) as demo:
                # Додаємо прихований стан для session_id
                session_state = gr.State(value=session_id)
                
                # Інтерфейс
                gr.Markdown("# 🎤 Advanced TTS System")
                gr.Markdown(f"**Session ID:** `{session_id}`")
                
                # Текстовий ввід
                text_input = gr.Textbox(
                    label="Введіть текст для синтезу",
                    placeholder="Введіть текст тут...",
                    lines=4,
                    interactive=True
                )
                
                # Обробка зміни тексту
                if self.handlers:
                    text_input.change(
                        fn=self.handlers.text_changed_handler,
                        inputs=[text_input],
                        outputs=[text_input]
                    )
                
                # Кнопка генерації
                generate_button = gr.Button("🎵 Згенерувати аудіо", variant="primary")
                
                # Аудіо вивід
                audio_output = gr.Audio(label="Згенероване аудіо")
                
                # Підключення TTS Engine, якщо він є
                if self.tts_engine and hasattr(self.tts_engine, 'synthesize'):
                    generate_button.click(
                        fn=self.tts_engine.synthesize,
                        inputs=[text_input],
                        outputs=[audio_output]
                    )
                    print("✅ TTS Engine підключено до інтерфейсу")
                else:
                    print("⚠️  TTS Engine не підключено до інтерфейсу")
                
                # Розділ для збереження
                with gr.Row():
                    save_button = gr.Button("💾 Зберегти аудіо", variant="secondary")
                    save_status = gr.Textbox(label="Статус збереження", interactive=False)
                
                # Підключення збереження
                if self.handlers:
                    save_button.click(
                        fn=self.handlers.save_audio_handler,
                        inputs=[audio_output, session_state],  # Передаємо session_state
                        outputs=[save_status]
                    )
                
            return demo
            
        except Exception as e:
            print(f"❌ Помилка створення UI: {e}")
            return None
    
    def create_simple_ui(self) -> gr.Blocks:
        """
        Створює простий інтерфейс (fallback)
        """
        with gr.Blocks(title="Simple TTS UI") as demo:
            gr.Markdown("# 🎤 TTS System")
            
            text_input = gr.Textbox(
                label="Текст для синтезу",
                placeholder="Введіть текст...",
                lines=3
            )
            
            generate_btn = gr.Button("Генерувати", variant="primary")
            audio_output = gr.Audio(label="Результат")
            
        return demo

if __name__ == "__main__":
    # Тестування
    print("AdvancedUIBuilder завантажено")