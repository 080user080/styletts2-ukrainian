import pathlib
from typing import List
from tqdm import tqdm
from services.google_translator import GoogleTranslator

class FileTranslationCommand:
    """Coordinates translation of text chunks and saving results."""
    def __init__(
        self,
        translator: GoogleTranslator,
        chunk_size: int = 4000
    ):
        self.translator = translator
        self.chunk_size = chunk_size

    def _split(self, text: str) -> List[str]:
        words = text.split()
        chunks, current, size = [], [], 0
        for word in words:
            add_len = len(word) + (1 if current else 0)
            if size + add_len > self.chunk_size:
                chunks.append(" ".join(current))
                current, size = [word], len(word)
            else:
                current.append(word)
                size += add_len
        if current:
            chunks.append(" ".join(current))
        return chunks

    def translate_text_to_file(
        self,
        text: str,
        output_path: pathlib.Path,
        source_lang: str,
        target_lang: str
    ):
        chunks = self._split(text)
        with output_path.open("w", encoding="utf-8") as f:
            for chunk in tqdm(chunks, desc="Translating", unit="chunk"):
                translated = self.translator.translate(chunk, source_lang, target_lang)
                f.write(translated + "\n")
                f.flush()

        print(f"✅ Done! Saved ► {output_path}")
