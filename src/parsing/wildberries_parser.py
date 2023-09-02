import re

from requests import Session

from src.models import Status, WildberriesUrls, WildberriesItem
from src.parsing import ItemParser
from src.utils import logger


class WildberriesParser(ItemParser):
    NO_SALE_AMOUNT = 0
    SALE_AMOUNT = 27
    DESTINATION = -1257786

    @staticmethod
    def get_items(urls: WildberriesUrls) -> list[WildberriesItem]:
        items = []

        for url in urls:
            logger.info(f"Getting item from \"{url}\"...")

            code = re.findall(r"catalog\/(\d+)", url)[0]

            try:
                quantity, sale_price, status = WildberriesParser._get_item_values(code, WildberriesParser.SALE_AMOUNT)
                _, no_sale_price, _ = WildberriesParser._get_item_values(code, WildberriesParser.NO_SALE_AMOUNT)
            except ValueError as e:
                logger.warning(e)
                continue

            item = WildberriesItem(
                url=url,
                quantity=quantity,
                sale_price=sale_price,
                no_sale_price=no_sale_price,
                status=status,
            )
            items.append(item)

            logger.info(f"Got item: {item}")

        return items

    @staticmethod
    def _get_item_values(code: str, sale_amount: int) -> tuple[int, int, Status]:
        with Session() as session:
            card_url = "https://card.wb.ru/cards/detail"
            params = {
                "nm": code,
                "spp": sale_amount,
                "dest": WildberriesParser.DESTINATION,
            }
            response = session.get(card_url, params=params)
        response_json = response.json()

        if not response_json.get("data").get("products"):
            raise ValueError(f"Item with code \"{code}\" not found")

        good = response_json.get("data").get("products")[0]
        price = int(good.get("salePriceU") / 100)

        status = Status.OUT_OF_STOCK
        quantity = 0
        stocks = good.get("sizes")[0].get("stocks")
        if stocks:
            quantity = sum([int(stock.get("qty")) for stock in stocks])
            status = Status.OK

        return quantity, price, status


def test_run():
    print(WildberriesParser.get_items(["https://www.wildberries.ru/catalog/74441434/detail.aspx"]))


if __name__ == '__main__':
    test_run()
