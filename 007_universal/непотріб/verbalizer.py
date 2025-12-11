
from transformers import MBartForConditionalGeneration, AutoTokenizer

verbalizer_model_name = "skypro1111/mbart-large-50-verbalization"


class Verbalizer():
    def __init__(self, device):
        self.device = device

        self.model = MBartForConditionalGeneration.from_pretrained(verbalizer_model_name,
            low_cpu_mem_usage=True,
            device_map=device,
        )
        self.model.eval()
    
        self.tokenizer = AutoTokenizer.from_pretrained(verbalizer_model_name)
        self.tokenizer.src_lang = "uk_XX"
        self.tokenizer.tgt_lang = "uk_XX"
    
    def generate_text(self, text):
        """Generate text for a single input."""
        # Prepare input
        input_text = "<verbalization>:" + text

        encoded_input = self.tokenizer(
            input_text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=1024,
        ).to(self.device)
        output_ids = self.model.generate(
            **encoded_input, max_length=1024, num_beams=5, early_stopping=True
        )
        normalized_text = self.tokenizer.decode(output_ids[0], skip_special_tokens=True)


        return normalized_text.strip()