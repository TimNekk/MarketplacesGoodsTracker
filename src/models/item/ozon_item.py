from dataclasses import dataclass

from src.models.item.item import Item
from src.models.status import Status


@dataclass
class OzonItem:
    url: str | None = None
    quantity: int = 0
    price: int = 0
    status: Status = Status.DEFAULT
    green_price: int | None = None


@dataclass
class OzonItemPair(Item):
    fbs: OzonItem
    fbo: OzonItem
