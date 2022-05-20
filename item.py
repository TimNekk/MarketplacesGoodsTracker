from dataclasses import dataclass

from status import Status


@dataclass
class Item:
    quantity: int = 0
    price: int = 0
    status: Status = Status.DEFAULT
