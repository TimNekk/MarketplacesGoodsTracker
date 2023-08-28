from abc import ABC, abstractmethod

from src.models import Item, Urls


class ItemParser(ABC):
    @staticmethod
    @abstractmethod
    def get_items(urls: Urls) -> list[Item]:
        pass
