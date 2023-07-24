from dataclasses import dataclass

from src.models.status import Status


@dataclass
class Item:
    url: str | None = None
    quantity: int = 0
    price: int = 0
    status: Status = Status.DEFAULT
    green_price: int | None = None
