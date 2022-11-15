import re

from requests import Session

from src.models import Item, Status
from src.parsing import ItemParser
from src.utils import logger


class WildberriesParser(ItemParser):
    SALE_AMOUNT = 27

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
                    "spp": WildberriesParser.SALE_AMOUNT
                }
                response = session.get(card_url, params=params)
                good = response.json().get("data").get("products")[0]
                option_id = good.get("sizes")[0].get("optionId")
                price = int(good.get("salePriceU") / 100)

                cart_url = "https://ru-basket-api.wildberries.ru/webapi/lk/basket/data"
                data = {
                    "basketItems[0][chrtId]": option_id,
                    "basketItems[0][cod1S]": code,
                }
                response = session.post(cart_url, data=data)

            quantity = int(response.json().get("value").get("data").get("basket").get("basketItems")[0].get("maxQuantity"))
            item = Item(
                id=code,
                quantity=quantity,
                price=price,
                status=Status.OK,
            )
            items.append(item)

            logger.info(f"Got item: {item}")

        return items


def test_run():
    print(WildberriesParser.get_items(["https://www.wildberries.ru/catalog/79674981/detail.aspx?targetUrl=XS",
                                       "https://www.wildberries.ru/catalog/79583779/detail.aspx?targetUrl=PB"]))


if __name__ == '__main__':
    test_run()