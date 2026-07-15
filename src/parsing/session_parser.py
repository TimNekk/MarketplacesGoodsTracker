from dataclasses import dataclass

from camoufox import Camoufox



@dataclass
class SessionData:
    cookies: dict[str, str]
    headers: dict[str, str]


def get_session(headless: bool = True) -> SessionData:
    with Camoufox(
        os="windows",
        headless="virtual",
        geoip=True,
        humanize=2.0,
    ) as browser:
        page = browser.new_page()

        with page.expect_request("**/api/entrypoint-api.bx/page/json/v2**", timeout=30000):
            page.goto("https://www.ozon.ru/?__rr=1&abt_att=1")

        cookies_list = page.context.cookies()
        cookies = {c["name"]: c["value"] for c in cookies_list}

        return SessionData(
            cookies=cookies,
            headers={'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36'},
        )
