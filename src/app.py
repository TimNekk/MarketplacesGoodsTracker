from time import sleep
from typing import List, Type

from oauth2client.service_account import ServiceAccountCredentials

from src.models import Item
from src.utils import logger
from src.parsing import ItemParser, OzonParser, RedirectParser
from src.sheets import Sheets


class App:
    def __init__(self, credentials: ServiceAccountCredentials):
        self.sheets = Sheets(credentials)

    def get_items(self, fix_redirects: bool = True) -> List[Item]:
        urls = self.sheets.get_urls() + [""]
        if fix_redirects:
            urls = self.fix_redirects_and_query(urls)
        logger.debug(f'Got urls: {urls}')

        parser: ItemParser = Type[OzonParser]
        return parser.get_items(urls)

    def fix_redirects_and_query(self, urls: List[str]) -> List[str]:
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

            logger.info("Exporting...\n")
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
