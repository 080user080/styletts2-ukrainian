from google import genai
from google.genai import types
import wave
import os
from tqdm import tqdm
from contracts.tts_service import TTSServiceInterface
from text_utils import split_to_sentence
import io
from pydub import AudioSegment

class GoogleTTS(TTSServiceInterface):
   def __init__(self, api_key: str, model: str, voice_name: str, pause_between_sentences: int = 50):
      self.client = genai.Client(api_key=api_key)
      self.model = model
      self.voice_name = voice_name
      self.pause_between_sentences = pause_between_sentences  # пауза в мілісекундах
      print(f"✅ Google TTS ініціалізовано з голосом: {voice_name}")
      print(f"   Пауза між реченнями: {pause_between_sentences}ms")

   def synthesize(self, text: str, max_duration: float | None = None):
      text = text.strip()
      sentences = self._preprocess_text(text)
      audio_chunks = []

      for sentence in tqdm(sentences, desc="Синтез Google TTS", unit="речення"):
         if not sentence:
            continue

         try:
            response = self.client.models.generate_content(
               model=self.model,
               contents=sentence,
               config=types.GenerateContentConfig(
                  response_modalities=["AUDIO"],
                  speech_config=types.SpeechConfig(
                     voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                           voice_name=self.voice_name,
                        )
                     )
                  ),
               )
            )
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            audio_chunks.append(audio_data)
         except Exception as error:
            print(f'❌ Помилка при озвученні: {error}\n→ Речення: "{sentence[:60]}"')
            continue

      if not audio_chunks:
         raise RuntimeError("Не вдалося озвучити жодне речення.")

      # Об'єднуємо всі аудіо чанки
      return self._combine_audio_chunks(audio_chunks)

   def synthesize_to_file(self, text: str, output_path: str, max_duration: float | None = None) -> None:
      self._validate_inputs(text, output_path)
      audio_data = self.synthesize(text, max_duration)
      
      # Визначаємо формат файлу за розширенням
      file_extension = os.path.splitext(output_path)[1].lower()
      
      if file_extension == '.wav':
         # Для WAV файлів використовуємо wave модуль
         self.wave_file(output_path, audio_data)
      elif file_extension in ['.mp3', '.m4a', '.ogg']:
         # Для інших форматів використовуємо pydub
         self._export_audio_file(output_path, audio_data, file_extension)
      else:
         # За замовчуванням зберігаємо як WAV
         if not output_path.endswith('.wav'):
            output_path = output_path + '.wav'
         self.wave_file(output_path, audio_data)
      
      print(f"✅ Аудіофайл збережено: {output_path}")

   def set_pause_between_sentences(self, pause_ms: int) -> None:
      """Налаштовує паузу між реченнями в мілісекундах."""
      self.pause_between_sentences = max(0, pause_ms)
      print(f"✅ Пауза між реченнями встановлена: {self.pause_between_sentences}ms")

   def get_audio_info(self, audio_data: bytes) -> dict:
      """Отримує інформацію про аудіо дані."""
      try:
         audio_segment = AudioSegment.from_wav(io.BytesIO(audio_data))
         return {
            "duration_ms": len(audio_segment),
            "sample_rate": audio_segment.frame_rate,
            "channels": audio_segment.channels,
            "sample_width": audio_segment.sample_width,
            "format": "WAV"
         }
      except Exception as e:
         return {"error": f"Не вдалося проаналізувати аудіо: {e}"}

   def _preprocess_text(self, text: str) -> list[str]:
      """Розбиває текст на речення для обробки."""
      return split_to_sentence(text)

   def _combine_audio_chunks(self, audio_chunks: list) -> bytes:
      """Об'єднує аудіо чанки в один безперервний аудіо потік."""
      if not audio_chunks:
         return b''
      
      if len(audio_chunks) == 1:
         return audio_chunks[0]
      
      try:
         # Конвертуємо кожен чанк в AudioSegment
         audio_segments = []
         total_duration = 0
         
         for i, chunk_data in enumerate(audio_chunks):
            try:
               # Google TTS повертає аудіо в форматі WAV або подібному
               # Спробуємо різні формати для конвертації
               audio_segment = None
               
               # Спробуємо як WAV
               try:
                  audio_segment = AudioSegment.from_wav(io.BytesIO(chunk_data))
               except:
                  pass
               
               # Спробуємо як MP3
               if audio_segment is None:
                  try:
                     audio_segment = AudioSegment.from_mp3(io.BytesIO(chunk_data))
                  except:
                     pass
               
               # Спробуємо як raw PCM (якщо це raw аудіо дані)
               if audio_segment is None:
                  try:
                     # Припускаємо 24kHz, 16-bit, mono як стандарт Google TTS
                     audio_segment = AudioSegment(
                        data=chunk_data,
                        sample_width=2,  # 16-bit
                        frame_rate=24000,  # 24kHz
                        channels=1  # mono
                     )
                  except:
                     pass
               
               if audio_segment is not None:
                  audio_segments.append(audio_segment)
                  total_duration += len(audio_segment)
                  print(f"✅ Чанк {i+1} конвертовано: {len(audio_segment)}ms")
               else:
                  print(f"⚠️ Не вдалося конвертувати чанк {i+1}")
                  
            except Exception as e:
               print(f"❌ Помилка при обробці чанку {i+1}: {e}")
               continue
         
         if not audio_segments:
            print("⚠️ Жоден аудіо чанк не вдалося конвертувати")
            return audio_chunks[0] if audio_chunks else b''
         
         # Об'єднуємо всі аудіо сегменти
         combined_audio = audio_segments[0]
         for segment in audio_segments[1:]:
            # Додаємо налаштовану паузу між реченнями
            if self.pause_between_sentences > 0:
               pause = AudioSegment.silent(duration=self.pause_between_sentences)
               combined_audio = combined_audio + pause + segment
            else:
               combined_audio = combined_audio + segment
         
         final_duration = len(combined_audio)
         pause_duration = self.pause_between_sentences * (len(audio_segments) - 1)
         
         print(f"✅ Об'єднано {len(audio_segments)} аудіо чанків в один потік")
         print(f"   Загальна тривалість: {final_duration}ms (аудіо: {total_duration}ms + паузи: {pause_duration}ms)")
         
         # Конвертуємо назад в bytes (WAV формат)
         output_buffer = io.BytesIO()
         combined_audio.export(output_buffer, format="wav")
         return output_buffer.getvalue()
         
      except Exception as e:
         print(f"❌ Помилка при об'єднанні аудіо: {e}")
         print("⚠️ Повертаємо перший чанк як fallback")
         return audio_chunks[0] if audio_chunks else b''

   def wave_file(self, filename, pcm, channels=1, rate=24000, sample_width=2):
      with wave.open(filename, "wb") as wf:
         wf.setnchannels(channels)
         wf.setsampwidth(sample_width)
         wf.setframerate(rate)
         wf.writeframes(pcm)

   def _export_audio_file(self, output_path: str, audio_data: bytes, format_type: str) -> None:
      """Експортує аудіо в різні формати за допомогою pydub."""
      try:
         # Конвертуємо bytes в AudioSegment
         audio_segment = AudioSegment.from_wav(io.BytesIO(audio_data))
         
         # Експортуємо в потрібний формат
         audio_segment.export(output_path, format=format_type[1:])  # Видаляємо крапку
         
      except Exception as e:
         print(f"❌ Помилка при експорті в {format_type}: {e}")
         print("⚠️ Зберігаємо як WAV замість цього")
         # Fallback до WAV
         wav_path = output_path.rsplit('.', 1)[0] + '.wav'
         self.wave_file(wav_path, audio_data)

   def _validate_inputs(self, text: str, output_path: str) -> None:
      if not text:
         raise ValueError("Текст не може бути порожнім.")
      if os.path.exists(output_path):
         raise FileExistsError(f"Файл вже існує: {output_path}")
