from paos.adapters.input.base import BaseInputAdapter
from paos.core.models import InputItem


class SocialMediaAdapter(BaseInputAdapter):
    """社交媒体输入适配器（预留占位）"""

    name = "social_media"

    def parse(self, raw_data: dict) -> InputItem:
        raise NotImplementedError("SocialMediaAdapter is not implemented yet")
