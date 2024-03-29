from dataclasses import dataclass

from src.models.urls import Urls


@dataclass
class WildberriesUrls(Urls):
    urls: list[str]

    def __iter__(self):
        return iter(self.urls)

    def __len__(self):
        return len(self.urls)
