import torch
from tqdm.auto import tqdm
from transformers import MBartForConditionalGeneration, AutoTokenizer
from text_utils import normalize, transliterate, split_to_sentence

class UkrainianVerbalizer:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = 'skypro1111/mbart-large-50-verbalization'

        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.tokenizer.src_lang = self.tokenizer.tgt_lang = "uk_XX"

        self.model = MBartForConditionalGeneration.from_pretrained(
            self.model_name,
            device_map="auto",
            low_cpu_mem_usage=True,
        )
        self.model.eval()

    def verbalize(self, text: str) -> str:
        """Вербалізує весь текст (розбиває на частини, обробляє, об'єднує)."""
        cleaned_text = self._preprocess_text(text)
        sentences = split_to_sentence(cleaned_text)

        results = [
            self._generate_verbalization(sentence)
            for sentence in tqdm(sentences, desc="Вербалізація", unit="частина")
        ]
        return " ".join(results)

    def _preprocess_text(self, text: str) -> str:
        text = normalize(text)
        return transliterate(text)

    def _generate_verbalization(self, sentence: str) -> str:
        input_text = f"<verbalization>:{sentence}"

        encoded_input = self.tokenizer(
            input_text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=1024
        ).to(self.device)

        with torch.no_grad():
            output_ids = self.model.generate(
                **encoded_input,
                max_length=1024,
                num_beams=5,
                early_stopping=True
            )

        return self.tokenizer.decode(output_ids[0], skip_special_tokens=True)