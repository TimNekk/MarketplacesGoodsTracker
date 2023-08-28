from dataclasses import dataclass

from src.parsing import ItemParser, OzonParser, WildberriesParser
from src.sheets import Sheets, OzonSheets, WildberriesSheets


@dataclass
class Marketplace:
    parser: type[ItemParser]
    sheets: type[Sheets]


OZON = Marketplace(
    parser=OzonParser,
    sheets=OzonSheets
)

WILDBERRIES = Marketplace(
    parser=WildberriesParser,
    sheets=WildberriesSheets
)
