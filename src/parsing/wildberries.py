import re

from requests import Session

from src.models import Item, Status
from src.parsing import ItemParser
from src.utils import logger


class WildberriesParser(ItemParser):
    SALE_AMOUNT = 27
    DESTINATION = -1257786

    @staticmethod
    def get_items(urls: list[str]) -> list[Item]:
        items = []

        for url in urls:
            logger.info(f"Getting item from \"{url}\"...")

            code = re.findall(r"catalog\/(\d+)", url)[0]

            with Session() as session:
                card_url = "https://card.wb.ru/cards/detail"
                params = {
                    "nm": code,
                    "spp": WildberriesParser.SALE_AMOUNT,
                    "dest": WildberriesParser.DESTINATION,
                }
                response = session.get(card_url, params=params)
            response_json = response.json()

            if not response_json.get("data").get("products"):
                continue

            good = response_json.get("data").get("products")[0]
            price = int(good.get("salePriceU") / 100)

            status = Status.OUT_OF_STOCK
            quantity = 0
            stocks = good.get("sizes")[0].get("stocks")
            if stocks:
                quantity = sum([int(stock.get("qty")) for stock in stocks])
                status = Status.OK

            item = Item(
                url=url,
                quantity=quantity,
                price=price,
                status=status,
            )
            items.append(item)

            logger.info(f"Got item: {item}")

        return items


def test_run():
    print(WildberriesParser.get_items(["https://www.wildberries.ru/catalog/41286685/detail.aspx"]))


if __name__ == '__main__':
    test_run()
