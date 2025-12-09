from youtube_transcript_api import YouTubeTranscriptApi
from typing import List, TypedDict
import re

class TranscriptEntry(TypedDict):
    text: str
    start: float
    duration: float
    end: float

class SubtitleParser:
    def _extract_id(self, url: str) -> str | None:
        pattern = (
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|v/|shorts/)|youtu\.be/)'
            r'([a-zA-Z0-9_-]{11})'
        )
        match = re.search(pattern, url)
        return match.group(1) if match else None

    def parse(self, url: str) -> List[TranscriptEntry]:
        video_id = self._extract_id(url)
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        result: List[TranscriptEntry] = []

        for i, entry in enumerate(transcript):
            start = entry["start"]
            duration = round(entry["duration"], 3)
            end = round(start + duration, 3)

            if i + 1 < len(transcript):
                next_start = transcript[i + 1]["start"]
                if end > next_start:
                    end = round(next_start, 3)
                    duration = round(end - start, 3)

            result.append({
                "text": entry["text"],
                "start": start,
                "duration": duration,
                "end": end
            })

        return result