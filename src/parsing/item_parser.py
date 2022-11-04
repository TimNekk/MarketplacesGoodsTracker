from abc import ABC, abstractmethod

from src.models import Item


class ItemParser(ABC):
    @staticmethod
    @abstractmethod
    def get_items(urls: list[str]) -> list[Item]:
        pass
