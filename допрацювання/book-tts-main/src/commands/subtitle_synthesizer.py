import webvtt
import numpy as np
from pydub import AudioSegment
from typing import Set
from tqdm import tqdm
from services.ukrainian_tts import UkrainianTTS

class SubtitleSynthesizer:
    def __init__(
        self,
        ukrainian_tts: UkrainianTTS,
        sample_rate: int = 24000,
        sample_width: int = 2,
        channels: int = 1,
    ):
        self.sample_rate = sample_rate
        self.ukrainian_tts = ukrainian_tts
        self.sample_width = sample_width
        self.channels = channels
        self.result_audio = AudioSegment.silent(duration=0)
        self.seen_lines: Set[str] = set()

    def synthesize(self, vtt_path: str, output_path: str):
        captions = list(webvtt.read(vtt_path))
        
        for caption in tqdm(captions, desc="Синтез субтитрів", unit="капшн"):
            start_ms = self._time_to_ms(caption.start)
            end_ms = self._time_to_ms(caption.end)
            text = caption.text.strip()

            if not text or text in self.seen_lines:
                continue
            self.seen_lines.add(text)

            duration = end_ms - start_ms
            if duration <= 0:
                continue

            pcm_array = self.ukrainian_tts.synthesize(text)
            raw_bytes = pcm_array.astype(np.int16).tobytes()

            speech = AudioSegment(
                data=raw_bytes,
                sample_width=self.sample_width,
                frame_rate=self.sample_rate,
                channels=self.channels,
            )

            speech = self._fit_audio_to_duration(speech, duration)

            if start_ms > len(self.result_audio):
                silence = AudioSegment.silent(duration=start_ms - len(self.result_audio))
                self.result_audio += silence

            self.result_audio += speech

        self.result_audio.export(output_path, format="mp3")
        print(f"✅ Saved to {output_path}")

    def _time_to_ms(self, t: str) -> int:
        h, m, s = t.split(":")
        s, ms = s.split(".")
        return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)

    def _fit_audio_to_duration(self, audio: AudioSegment, target_ms: int) -> AudioSegment:
        if len(audio) == 0:
            return AudioSegment.silent(duration=target_ms)
        return audio._spawn(audio.raw_data, overrides={
            "frame_rate": int(audio.frame_rate * len(audio) / target_ms)
        }).set_frame_rate(audio.frame_rate)