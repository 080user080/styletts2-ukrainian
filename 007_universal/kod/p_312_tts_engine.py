# p_312_tts_engine.py - TTSEngine з конвертацією config в dict

from typing import Dict, Any
from types import SimpleNamespace
import logging
import numpy as np
import torch

class TTSEngine:
    def __init__(self, app_context: Dict[str, Any]):
        self.app_context = app_context
        self.config = app_context.get('config', {})
        # Якщо config — pydantic або інший об'єкт, спробуємо перетворити в dict
        if not isinstance(self.config, dict):
            try:
                self.config = self.config.dict()
            except Exception:
                # якщо не вийшло — залишаємо як є (будемо звертатись обережно)
                pass
        self.is_initialized = False
        self.logger = app_context.get('logger', logging.getLogger("TTSEngine"))

    def initialize(self) -> bool:
        try:
            self.is_initialized = True
            self.app_context['tts_engine'] = self
            self.logger.info("Ініціалізація TTSEngine завершена")
            return True
        except Exception as e:
            self.logger.error(f"Не вдалося ініціалізувати TTSEngine: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        return {
            'initialized': self.is_initialized,
            'models_loaded': bool(self.app_context.get('tts_models')),
            'verbalizer': bool(self.app_context.get('verbalizer'))
        }

    def synthesize(self, text: str, speaker_id: int = 1, speed: float = None,
                   voice: str = None) -> SimpleNamespace:
        if not self.is_initialized and not self.initialize():
            raise RuntimeError("TTSEngine не ініціалізовано")

        # Безпечне отримання значень з config (тут config — dict або об'єкт)
        def cfg_get(key, default=None):
            try:
                if isinstance(self.config, dict):
                    return self.config.get(key, default)
                # якщо config — об'єкт (pydantic), спробуємо атрибут
                return getattr(self.config, key, default)
            except Exception:
                return default

        if speed is None:
            speed = cfg_get('tts', {}).get('default_speed', 0.88) if isinstance(cfg_get('tts', {}), dict) else getattr(cfg_get('tts', {}), 'default_speed', 0.88)

        logger = self.app_context.get('logger', logging.getLogger("TTSEngine"))
        logger.info(f"Синтез: {len(text)} символів, спікер: {speaker_id}, швидкість: {speed}, голос: {voice}")

        try:
            tts_models = self.app_context.get('tts_models')
            if not tts_models:
                logger.error("TTS моделі не знайдені в контексті — повертаю тестове аудіо")
                return self._generate_test_audio(text, speed)

            verbalizer = self.app_context.get('verbalizer')

            processed_text = text
            if verbalizer and any(c.isdigit() for c in text):
                try:
                    processed_text = verbalizer.generate_text(text)
                except Exception as e:
                    logger.warning(f"Помилка вербалізації: {e}")

            if hasattr(self, 'normalize_text'):
                processed_text = self.normalize_text(processed_text)
            parts = self.split_to_parts(processed_text) if hasattr(self, 'split_to_parts') else [processed_text]

            all_audio = []
            sample_rate = cfg_get('tts', {}).get('sample_rate', 24000) if isinstance(cfg_get('tts', {}), dict) else getattr(cfg_get('tts', {}), 'sample_rate', 24000)

            for i, part_text in enumerate(parts):
                logger.debug(f"Синтез частини {i+1}/{len(parts)}: {len(part_text)} символів")
                try:
                    if voice and hasattr(tts_models, 'get_multi_model'):
                        model, style = tts_models.get_multi_model(voice)
                    elif hasattr(tts_models, 'get_single_model'):
                        model, style = tts_models.get_single_model()
                    else:
                        logger.error("Менеджер моделей не має очікуваних методів")
                        return self._generate_test_audio(text, speed)

                    try:
                        from ipa_uk import ipa
                        from ukrainian_word_stress import Stressifier, StressSymbol
                        import re
                        from unicodedata import normalize

                        stressify = Stressifier()
                        t = part_text.replace('+', StressSymbol.CombiningAcuteAccent)
                        t = normalize('NFKC', t)
                        t = re.sub(r'[᠆‐‑‒–—―⁻₋−⸺⸻]', '-', t)
                        t = re.sub(r' - ', ': ', t)

                        ps = ipa(stressify(t))
                        if not ps:
                            logger.warning("Не вдалося згенерувати IPA для частини")
                            continue

                        tokens = model.tokenizer.encode(ps)
                        wav = model(tokens, speed=speed, s_prev=style)

                        if hasattr(wav, 'cpu'):
                            wav = wav.cpu()
                        audio_part = wav.numpy() if isinstance(wav, torch.Tensor) else np.array(wav)
                        all_audio.append(audio_part)

                    except ImportError as e:
                        logger.error(f"Відсутні залежності для синтезу: {e}")
                        return self._generate_test_audio(text, speed)
                    except Exception as e:
                        logger.error(f"Помилка під час синтезу частини: {e}")
                        continue

                except Exception as e:
                    logger.error(f"Помилка обробки частини {i+1}: {e}")
                    continue

            if not all_audio:
                raise RuntimeError("Не вдалося синтезувати жодну частину")

            concatenated = np.concatenate(all_audio)
            duration = len(concatenated) / sample_rate

            output_path = None
            tts_cfg = cfg_get('tts', {})
            autosave = (tts_cfg.get('autosave', True) if isinstance(tts_cfg, dict) else getattr(tts_cfg, 'autosave', True))
            if autosave and hasattr(self, '_save_audio'):
                output_path = self._save_audio(concatenated, sample_rate, speaker_id)

            result_dict = {
                'audio': concatenated,
                'sample_rate': sample_rate,
                'duration': duration,
                'speaker_id': speaker_id,
                'speed': speed,
                'voice': voice,
                'output_path': output_path,
                'text': text,
                'processed_text': processed_text,
                'is_test': False
            }
            return result_dict

        except Exception as e:
            logger.error(f"Критична помилка синтезу: {e}")
            import traceback
            traceback.print_exc()
            return self._generate_test_audio(text, speed)

    def _generate_test_audio(self, text: str, speed: float) -> SimpleNamespace:
        sample_rate = 24000
        try:
            tts_cfg = self.config if isinstance(self.config, dict) else (self.config if hasattr(self.config, 'tts') else {})
            sample_rate = tts_cfg.get('sample_rate', 24000) if isinstance(tts_cfg, dict) else getattr(tts_cfg, 'sample_rate', 24000)
        except Exception:
            sample_rate = 24000

        duration = max(0.5, min(len(text) / 50, 10.0))
        base_freq = 220 + (hash(text) % 880)
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = 0.3 * np.sin(2 * np.pi * base_freq * t)
        audio += 0.1 * np.sin(2 * np.pi * base_freq * 1.5 * t)
        audio += 0.05 * np.sin(2 * np.pi * base_freq * 2 * t)
        fade_samples = int(0.05 * sample_rate)
        if len(audio) > fade_samples:
            fade_in = np.linspace(0, 1, fade_samples)
            fade_out = np.linspace(1, 0, fade_samples)
            audio[:fade_samples] *= fade_in
            audio[-fade_samples:] *= fade_out
        audio = audio / np.max(np.abs(audio)) * 0.5
        result = {
            'audio': audio,
            'sample_rate': sample_rate,
            'duration': duration,
            'speaker_id': 1,
            'speed': speed,
            'voice': 'test',
            'output_path': None,
            'is_test': True
        }
        return result

# Сумісність з loader
def initialize(app_context: Dict[str, Any]) -> Dict[str, Any]:
    engine = TTSEngine(app_context)
    ok = engine.initialize()
    return {"status": "ok" if ok else "error", "engine": engine}