import time

from camoufox import Camoufox

from src.parsing.ozon_session_parser import SessionData

TOKEN_COOKIE_NAME = "x_wbaas_token"
TOKEN_WAIT_TIMEOUT_SEC = 30


def get_session(headless: bool = True) -> SessionData:
    with Camoufox(
        os="windows",
        headless="virtual",
        geoip=True,
        humanize=2.0,
    ) as browser:
        page = browser.new_page()
        page.goto("https://www.wildberries.ru/")

        cookies = {}
        deadline = time.monotonic() + TOKEN_WAIT_TIMEOUT_SEC
        while TOKEN_COOKIE_NAME not in cookies:
            if time.monotonic() > deadline:
                raise TimeoutError(f"Timed out waiting for \"{TOKEN_COOKIE_NAME}\" cookie")
            cookies = {c["name"]: c["value"] for c in page.context.cookies()}
            page.wait_for_timeout(500)

        return SessionData(
            cookies=cookies,
            headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'},
        )
