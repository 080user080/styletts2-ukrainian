import os
import torch
import soundfile as sf
from tqdm import tqdm
from ipa_uk import ipa
from styletts2_inference.models import StyleTTS2
from ukrainian_word_stress import Stressifier
from text_utils import (
    text_cleaner,
    normalize,
    split_to_sentence,
    replace_numbers_with_words
)

SAMPLE_RATE = 24000

class UkrainianTTS:
    def __init__(self, prompt_audio: str):
        self.prompt_audio = prompt_audio
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = StyleTTS2(hf_path='patriotyk/styletts2_ukrainian_multispeaker', device=self.device)
        self.stressifier = Stressifier()
        print(f"✅ Модель завантажено на {self.device}")

    def synthesize(self, text: str, max_duration: float | None = None):
        text = text.strip()
        sentences = self._preprocess_text(text)
        audio_chunks = []

        speed = 1.0
        if max_duration is not None:
            # Попередня оцінка: синтез при стандартній швидкості
            audio_chunks = self._synthesize_sentences(sentences, speed=1.0)
            total_duration = self._estimate_duration(audio_chunks)

            if total_duration > max_duration:
                speed = total_duration / max_duration
                print(f"⚠️ Аудіо задовге: {total_duration:.2f}s > {max_duration:.2f}s. Прискорюємо до x{speed:.2f}")
                audio_chunks = self._synthesize_sentences(sentences, speed=speed)
        else:
            audio_chunks = self._synthesize_sentences(sentences, speed=1.0)

        duration = self._estimate_duration(audio_chunks)

        return torch.cat(audio_chunks).cpu().numpy(), duration

    def synthesize_to_file(self, text: str, output_path: str, max_duration: float | None = None) -> None:
        self._validate_inputs(text, output_path)
        audio_data, duration = self.synthesize(text, max_duration)
        sf.write(output_path, audio_data, SAMPLE_RATE)
        print(f"✅ Аудіофайл збережено: {output_path}")

    def _validate_inputs(self, text: str, output_path: str) -> None:
        if not text:
            raise ValueError("Текст не може бути порожнім.")
        if os.path.exists(output_path):
            raise FileExistsError(f"Файл вже існує: {output_path}")

    def _preprocess_text(self, text: str) -> list[str]:
        text = normalize(text)
        text = replace_numbers_with_words(text)
        return split_to_sentence(text)

    def _process_sentence(self, sentence: str) -> torch.Tensor | None:
        stressed = self.stressifier(sentence)
        ipa_text = ipa(stressed)
        cleaned = text_cleaner(ipa_text)
        if not cleaned:
            return None
        return torch.LongTensor(cleaned).to(self.device)

    def _synthesize_sentences(self, sentences: list[str], speed: float) -> list[torch.Tensor]:
        chunks = []
        for sentence in tqdm(sentences, desc="Синтез", unit="речення"):
            tokens = self._process_sentence(sentence)
            if tokens is None:
                print(f'⚠️ Пропущено: {sentence[:60]}...')
                continue
            try:
                style_vector = self.model.predict_style_multi(self.prompt_audio, tokens).to(self.device)
                audio = self.model(tokens, speed=speed, s_prev=style_vector)
                chunks.append(audio)
            except Exception as error:
                print(f'❌ Помилка при озвученні: {error}\n→ Речення: "{sentence[:60]}"')
        return chunks

    def _estimate_duration(self, audio_chunks: list[torch.Tensor]) -> float:
        samples = sum(chunk.shape[-1] for chunk in audio_chunks)
        return samples / SAMPLE_RATE
