from time import sleep

from oauth2client.service_account import ServiceAccountCredentials

from src.models import Item
from src.utils import logger
from src.parsing import ItemParser, OzonParser, RedirectParser, WildberriesParser
from src.sheets import Sheets


class App:
    def __init__(self, credentials: ServiceAccountCredentials):
        self.sheets = Sheets(credentials)

    def get_items(self, fix_redirects: bool = True) -> list[Item]:
        urls = self.sheets.get_urls() + [""]
        if fix_redirects:
            urls = self.fix_redirects_and_query(urls)
        logger.debug(f'Got urls: {urls}')

        sorted_urls: dict[type[ItemParser], list[str]] = {
            WildberriesParser: [url for url in urls if "wildberries.ru" in url],
            OzonParser: [url for url in urls if "ozon.ru" in url]
        }

        items = []
        for parser, urls in sorted_urls.items():
            if not urls:
                continue

            logger.info(f"Getting items from {parser.__name__}...")
            item = parser.get_items(urls)
            items.extend(item)

        return items

    def fix_redirects_and_query(self, urls: list[str]) -> list[str]:
        logger.info("Fixing redirects...")
        with RedirectParser() as parser:
            for index, old_url in enumerate(urls):
                if not old_url:
                    continue

                logger.debug(f"Checking \"{old_url}\"...")
                urls[index] = parser.remove_query_from_url(urls[index])
                redirect = parser.get_redirect(urls[index])

                if redirect != urls[index] and "ozon.ru/search/" not in redirect:
                    urls[index] = parser.remove_query_from_url(redirect)

                if old_url != urls[index]:
                    self.sheets.replace_url(old_url, urls[index])

        return urls

    def update(self, fix_redirects: bool = True):
        try:
            logger.info("Getting items...")
            while True:
                try:
                    items = self.get_items(fix_redirects)
                    logger.debug("\n".join(map(str, items)))
                    break
                except Exception as e:
                    logger.exception(e)

            logger.info("Exporting...")
            while True:
                try:
                    self.sheets.set_items(items)
                    break
                except Exception as e:
                    logger.exception(e)
                    sleep(60)

            logger.info("Done exporting!")
        except Exception as e:
            logger.exception(e)
