import os
import shutil
import time
import uuid
from dataclasses import dataclass

from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth

from src.utils import logger


@dataclass
class SessionData:
    cookies: dict[str, str]
    headers: dict[str, str]


def _cleanup_seleniumwire_storage(storage_path: str) -> None:
    """Clean up seleniumwire temporary storage."""
    try:
        if os.path.exists(storage_path):
            shutil.rmtree(storage_path)
            logger.debug(f"Cleaned up seleniumwire storage: {storage_path}")
    except Exception as e:
        logger.warning(f"Failed to clean up seleniumwire storage: {e}")


def get_session(headless: bool = True) -> SessionData:
    """Fetch fresh session cookies and headers from Ozon using Selenium."""
    logger.info("Fetching new Ozon session...")

    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--incognito")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=ru-RU")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Use unique storage path for seleniumwire to avoid conflicts/corruption
    storage_path = f"/tmp/.seleniumwire-{uuid.uuid4().hex[:8]}"
    seleniumwire_options = {
        "request_storage_base_dir": storage_path,
        "exclude_hosts": [],  # Don't exclude any hosts
    }

    driver = webdriver.Chrome(options=options, seleniumwire_options=seleniumwire_options)

    stealth(
        driver,
        languages=["ru-RU", "ru"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    try:
        driver.get("https://www.ozon.ru/?__rr=1&abt_att=1")
        driver.wait_for_request("/api/entrypoint-api.bx/page/json/v2", timeout=30)

        cookies_list = driver.get_cookies()
        cookies = {c["name"]: c["value"] for c in cookies_list}
        user_agent = driver.execute_script("return navigator.userAgent")

        headers = {
            "Accept": "application/json",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Referer": "https://www.ozon.ru/",
            "Origin": "https://www.ozon.ru",
            "User-Agent": user_agent,
        }

        try:
            sec_ch_ua = driver.execute_script("""
                const ua = navigator.userAgent;
                const match = ua.match(/Chrome\\/(\\d+)/);
                if (match) {
                    const ver = match[1];
                    return `"Chromium";v="${ver}", "Google Chrome";v="${ver}", "Not-A.Brand";v="99"`;
                }
                return '"Chromium";v="120", "Google Chrome";v="120", "Not-A.Brand";v="99"';
            """)
            headers["sec-ch-ua"] = sec_ch_ua
        except Exception:
            headers["sec-ch-ua"] = (
                '"Chromium";v="120", "Google Chrome";v="120", "Not-A.Brand";v="99"'
            )

        logger.info("Session fetched successfully")
        return SessionData(cookies=cookies, headers=headers)

    finally:
        try:
            driver.quit()
        except Exception:
            pass
        # Clean up seleniumwire storage to prevent accumulation
        _cleanup_seleniumwire_storage(storage_path)
