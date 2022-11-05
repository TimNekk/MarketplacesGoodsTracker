import re

from requests import Session

from src.models import Item, Status
from src.parsing import ItemParser


class WildberriesParser(ItemParser):
    @staticmethod
    def get_items(urls: list[str]) -> list[Item]:
        items = []

        for url in urls:
            code = re.findall(r"catalog\/(\d+)", url)[0]

            with Session() as session:
                card_url = "https://card.wb.ru/cards/detail"
                params = {"nm": code}
                response = session.get(card_url, params=params)
                option_id = response.json().get("data").get("products")[0].get("sizes")[0].get("optionId")

                cart_url = "https://ru-basket-api.wildberries.ru/webapi/lk/basket/data"
                data = {
                    "basketItems[0][chrtId]": option_id,
                    "basketItems[0][cod1S]": code,
                }
                response = session.post(cart_url, data=data)

            good = response.json().get("value").get("data").get("basket").get("basketItems")[0]
            item = Item(
                id=code,
                quantity=int(good.get("maxQuantity")),
                price=int(good.get("price")),
                status=Status.OK,
            )
            items.append(item)

        return items


def test_run():
    print(WildberriesParser.get_items(["https://www.wildberries.ru/catalog/79674981/detail.aspx?targetUrl=XS",
                                       "https://www.wildberries.ru/catalog/79583779/detail.aspx?targetUrl=PB"]))


if __name__ == '__main__':
    test_run()
