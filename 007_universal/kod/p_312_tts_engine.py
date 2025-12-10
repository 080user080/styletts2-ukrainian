# p_312_tts_engine.py (оновлений метод synthesize)

def synthesize(self, text: str, speaker_id: int = 1, speed: float = None, 
               voice: str = None) -> Dict[str, Any]:
    """
    Основний метод синтезу з використанням справжніх TTS моделей.
    
    Args:
        text: Текст для синтезу
        speaker_id: ID спікера (1-30)
        speed: Швидкість синтезу (0.7-1.3)
        voice: Назва голосу (для multi моделі)
        
    Returns:
        Dict з результатами синтезу
    """
    if not self.is_initialized and not self.initialize():
        raise RuntimeError("TTSEngine не ініціалізовано")
    
    if speed is None:
        speed = self.config['tts'].get('default_speed', 0.88)
    
    logger = self.app_context.get('logger', logging.getLogger("TTSEngine"))
    logger.info(f"Синтез: {len(text)} символів, спікер: {speaker_id}, швидкість: {speed}, голос: {voice}")
    
    try:
        # 1. Отримати менеджер моделей TTS
        tts_models = self.app_context.get('tts_models')
        if not tts_models:
            logger.error("TTS моделі не знайдені в контексті")
            return self._generate_test_audio(text, speed)
        
        # 2. Отримати verbalizer (якщо доступний)
        verbalizer = self.app_context.get('verbalizer')
        
        # 3. Обробити текст (вербалізація, якщо потрібно)
        processed_text = text
        if verbalizer and any(c.isdigit() for c in text):
            try:
                processed_text = verbalizer.generate_text(text)
                logger.debug(f"Текст вербалізовано: {processed_text[:100]}...")
            except Exception as e:
                logger.warning(f"Помилка вербалізації: {e}")
        
        # 4. Нормалізація тексту
        processed_text = self.normalize_text(processed_text)
        
        # 5. Розбиття на частини (якщо потрібно)
        parts = self.split_to_parts(processed_text)
        
        # 6. Синтез кожної частини
        all_audio = []
        sample_rate = self.config['tts'].get('sample_rate', 24000)
        
        for i, part_text in enumerate(parts):
            logger.debug(f"Синтез частини {i+1}/{len(parts)}: {len(part_text)} символів")
            
            try:
                # Отримати модель та стиль
                if voice:
                    # Використовувати multi модель з вибраним голосом
                    model, style = tts_models.get_multi_model(voice)
                    if not style:
                        raise RuntimeError(f"Стиль для голосу '{voice}' не знайдено")
                else:
                    # Використовувати single модель
                    model, style = tts_models.get_single_model()
                    if not style:
                        raise RuntimeError("Single стиль не завантажено")
                
                # Підготувати текст для синтезу
                # Тут потрібна обробка тексту (IPA, наголоси тощо)
                # Для початку - проста реалізація
                
                # Виклик моделі для синтезу (замість заглушки)
                # Це спрощена версія, потрібно адаптувати з оригінального коду
                
                # Імпортуємо необхідні модулі для обробки тексту
                try:
                    from ipa_uk import ipa
                    from ukrainian_word_stress import Stressifier, StressSymbol
                    import re
                    from unicodedata import normalize
                    
                    # Обробка тексту (як у p_305_tts_gradio_main.py)
                    stressify = Stressifier()
                    t = part_text.replace('+', StressSymbol.CombiningAcuteAccent)
                    t = normalize('NFKC', t)
                    t = re.sub(r'[᠆‐‑‒–—―⁻₋−⸺⸻]', '-', t)
                    t = re.sub(r' - ', ': ', t)
                    
                    # Конвертація в IPA
                    ps = ipa(stressify(t))
                    
                    if not ps:
                        logger.warning(f"Не вдалося конвертувати в IPA: {part_text[:50]}...")
                        continue
                    
                    # Токенізація та синтез
                    tokens = model.tokenizer.encode(ps)
                    wav = model(tokens, speed=speed, s_prev=style)
                    
                    # Перетворення в numpy array
                    if hasattr(wav, 'cpu'):
                        wav = wav.cpu()
                    
                    audio_part = wav.numpy() if isinstance(wav, torch.Tensor) else np.array(wav)
                    all_audio.append(audio_part)
                    
                except ImportError as e:
                    logger.error(f"Відсутні залежності для синтезу: {e}")
                    return self._generate_test_audio(text, speed)
                except Exception as e:
                    logger.error(f"Помилка синтезу частини: {e}")
                    continue
                
            except Exception as e:
                logger.error(f"Помилка обробки частини {i+1}: {e}")
                continue
        
        # 7. Об'єднати всі частини
        if not all_audio:
            raise RuntimeError("Не вдалося синтезувати жодну частину")
        
        concatenated = np.concatenate(all_audio)
        duration = len(concatenated) / sample_rate
        
        # 8. Зберегти результат (якщо налаштовано)
        output_path = None
        if self.config['tts'].get('autosave', True):
            output_path = self._save_audio(concatenated, sample_rate, speaker_id)
        
        # 9. Повернути результат
        return {
            'audio': concatenated,
            'sample_rate': sample_rate,
            'duration': duration,
            'speaker_id': speaker_id,
            'speed': speed,
            'voice': voice,
            'output_path': output_path,
            'text': text,
            'processed_text': processed_text
        }
        
    except Exception as e:
        logger.error(f"Критична помилка синтезу: {e}")
        import traceback
        traceback.print_exc()
        # Fallback до тестового аудіо
        return self._generate_test_audio(text, speed)

def _generate_test_audio(self, text: str, speed: float) -> Dict[str, Any]:
    """
    Генерує тестове аудіо (синусоїду) для відлагодження.
    Використовується лише як fallback.
    """
    sample_rate = self.config['tts'].get('sample_rate', 24000)
    duration = max(0.5, min(len(text) / 50, 10.0))  # Обмежити тривалість
    
    # Різні частоти для різних спікерів
    base_freq = 220 + (hash(text) % 880)
    
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Більш складна хвиля для більш природнього звуку
    audio = 0.3 * np.sin(2 * np.pi * base_freq * t)
    audio += 0.1 * np.sin(2 * np.pi * base_freq * 1.5 * t)
    audio += 0.05 * np.sin(2 * np.pi * base_freq * 2 * t)
    
    # Затухання
    fade_samples = int(0.05 * sample_rate)
    if len(audio) > fade_samples:
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        audio[:fade_samples] *= fade_in
        audio[-fade_samples:] *= fade_out
    
    # Нормалізація
    audio = audio / np.max(np.abs(audio)) * 0.5
    
    return {
        'audio': audio,
        'sample_rate': sample_rate,
        'duration': duration,
        'speaker_id': 1,
        'speed': speed,
        'voice': 'test',
        'output_path': None,
        'is_test': True
    }