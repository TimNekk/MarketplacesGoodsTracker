import re

from requests import Session

from src.models import Status, WildberriesUrls, WildberriesItem
from src.parsing import ItemParser
from src.utils import logger


class WildberriesParser(ItemParser):
    NO_SALE_AMOUNT = 0
    SALE_AMOUNT = 30
    DESTINATION = -1257786
    HEADERS = {
        'accept': '*/*',
        'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'deviceid': 'site_9aac2961cc744827a5d16b84c6c004e3',
        'priority': 'u=1, i',
        'referer': 'https://www.wildberries.ru/catalog/14922314/detail.aspx',
        'sec-ch-ua': '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
        'x-spa-version': '14.19.3',
    }
    COOKIES = {
        'x_wbaas_token': '1.1000.877ba0390b234b61991457eaed767967.MHw0Ni4xODguODIuMTF8TW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzE1MS4wLjAuMCBTYWZhcmkvNTM3LjM2fDE3ODY3OTE3ODd8cmV1c2FibGV8MnxleUpvWVhOb0lqb2lJbjA9fDF8M3wxNzg2NjYyMTg3fDE=.MEUCIQDQ8oQM0wQv96A22C0qLsAqY4TVMoRR7qfxQkxJ3wt8ewIgFLNq2HHHCJQ97fL/MKVRX19/3TCdeDxmIIpn9MDqb7I=',
    }

    @staticmethod
    def get_items(urls: WildberriesUrls) -> list[WildberriesItem]:
        items = []

        for url in urls:
            logger.info(f"Getting item from \"{url}\"...")

            code = re.findall(r"catalog\/(\d+)", url)[0]

            try:
                quantity, price, status = WildberriesParser._get_item_values(code, WildberriesParser.SALE_AMOUNT)
            except ValueError as e:
                logger.warning(e)
                continue

            item = WildberriesItem(
                url=url,
                quantity=quantity,
                sale_price=int(price * 0.98),
                no_sale_price=int(price),
                status=status,
            )
            items.append(item)

            logger.info(f"Got item: {item}")

        return items

    @staticmethod
    def _get_item_values(code: str, sale_amount: int) -> tuple[int, int, Status]:
        with Session() as session:
            card_url = "https://www.wildberries.ru/__internal/u-card/cards/v4/detail"
            params = {
                "nm": code,
                "spp": sale_amount,
                "dest": WildberriesParser.DESTINATION,
            }
            response = session.get(
                card_url, 
                params=params,
                headers=WildberriesParser.HEADERS,
                cookies=WildberriesParser.COOKIES,
            )
        response_json = response.json()

        if not response_json.get("products"):
            raise ValueError(f"Item with code \"{code}\" not found")

        good = response_json.get("products", [])[0]
        price = int(good.get("sizes", [])[0].get("price", {}).get("product") / 100)

        status = Status.OUT_OF_STOCK
        quantity = 0
        stocks = good.get("sizes", [])[0].get("stocks", [])
        if stocks:
            quantity = sum([int(stock.get("qty")) for stock in stocks])
            status = Status.OK

        return quantity, price, status


def test_run():
    print(WildberriesParser.get_items(["https://www.wildberries.ru/catalog/74441434/detail.aspx"]))


if __name__ == '__main__':
    test_run()
