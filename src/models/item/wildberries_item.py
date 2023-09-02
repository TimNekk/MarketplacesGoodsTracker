from dataclasses import dataclass

from src.models.item.item import Item
from src.models.status import Status


@dataclass
class WildberriesItem(Item):
    url: str | None = None
    quantity: int = 0
    sale_price: int = 0
    no_sale_price: int = 0
    status: Status = Status.DEFAULT

    @property
    def sale_formula(self) -> str:
        return f"=({self.no_sale_price} - {self.sale_price}) / {self.no_sale_price}"
