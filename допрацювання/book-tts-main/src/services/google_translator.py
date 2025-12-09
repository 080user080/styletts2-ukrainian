from google.cloud import translate_v3 as translate

class GoogleTranslator:
    """Service to translate a single chunk using Google Cloud Translation API."""
    def __init__(self, project_id: str, location: str = "global"):
        self.client = translate.TranslationServiceClient()
        self.parent = f"projects/{project_id}/locations/{location}"

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        response = self.client.translate_text(
            parent=self.parent,
            contents=[text],
            mime_type="text/plain",
            source_language_code=source_lang,
            target_language_code=target_lang,
        )
        return response.translations[0].translated_text