from paos.adapters.input.base import BaseInputAdapter
from paos.core.models import InputItem


class NaturalLanguageAdapter(BaseInputAdapter):
    name = "natural_language"

    def parse(self, raw_data: dict) -> InputItem:
        content = raw_data.get("content", "")
        if not content:
            raise ValueError("Content is required for natural_language input")
        return InputItem(
            source=self.name,
            content=content,
            metadata=raw_data.get("metadata", {}),
        )
