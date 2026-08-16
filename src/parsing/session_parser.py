from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from camoufox import Camoufox
from playwright.sync_api import BrowserContext

from src.utils import logger

DATA_DIR = Path(os.getenv("OZON_DATA_DIR", "data"))

# Persistent Firefox profile holding the Ozon login. Ozon rotates the auth
# tokens itself every time this profile visits the site, so the session stays
# alive without touching any refresh endpoint.
PROFILE_DIR = Path(os.getenv("OZON_PROFILE_DIR", str(DATA_DIR / "ozon_profile")))

# Fingerprint of that profile. Reused on every launch: rotating the fingerprint
# under an authenticated cookie set is what gets the session invalidated.
FINGERPRINT_PATH = Path(
    os.getenv("OZON_FINGERPRINT_PATH", str(DATA_DIR / "ozon_fingerprint.json"))
)

OZON_URL = "https://www.ozon.ru/?__rr=1&abt_att=1"
ENTRYPOINT_REQUEST = "**/api/entrypoint-api.bx/page/json/v2**"
REQUEST_TIMEOUT_MS = 30000

USER_ID_COOKIE = "__Secure-user-id"
ANONYMOUS_USER_IDS = ("", "0")

# Config keys derived from the current IP address rather than from the
# fingerprint. Dropped before reuse so they are regenerated for whatever
# machine/IP the profile is running on.
VOLATILE_CONFIG_PREFIXES = ("webrtc:", "geolocation:")


@dataclass
class SessionData:
    cookies: dict[str, str]
    headers: dict[str, str]

    @property
    def is_authenticated(self) -> bool:
        """Whether the session belongs to a logged in account.

        Anonymous sessions also carry `__Secure-access-token`, so token
        presence is not an auth signal - the user id is.
        """
        return self.cookies.get(USER_ID_COOKIE, "0") not in ANONYMOUS_USER_IDS


def _load_fingerprint() -> dict[str, Any]:
    if not FINGERPRINT_PATH.exists():
        logger.info(f"No saved fingerprint at {FINGERPRINT_PATH}, generating a new one")
        return {}

    config = json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8"))
    return {
        key: value
        for key, value in config.items()
        if not key.startswith(VOLATILE_CONFIG_PREFIXES)
    }


def _save_fingerprint(config: dict[str, Any]) -> None:
    FINGERPRINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    FINGERPRINT_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    logger.info(f"Saved fingerprint to {FINGERPRINT_PATH}")


@contextmanager
def open_profile(headless: bool | str = "virtual") -> Iterator[BrowserContext]:
    """Open the persistent Ozon profile.

    Camoufox fills the passed config dict in place, so on the first run it is
    saved afterwards and reused verbatim on every later launch.
    """
    config = _load_fingerprint()
    is_new_fingerprint = not config

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with Camoufox(
        persistent_context=True,
        user_data_dir=str(PROFILE_DIR),
        config=config,
        os="windows",
        headless=headless,
        geoip=True,
        humanize=2.0,
        i_know_what_im_doing=True,
    ) as context:
        yield context

    if is_new_fingerprint:
        _save_fingerprint(config)


def _headless_mode(headless: bool) -> bool | str:
    if not headless:
        return False
    # The Xvfb backed headful mode only exists on Linux (the container), local
    # runs on Windows/macOS fall back to real headless.
    return "virtual" if sys.platform.startswith("linux") else True


def get_session(headless: bool = True) -> SessionData:
    with open_profile(_headless_mode(headless)) as context:
        page = context.pages[0] if context.pages else context.new_page()

        with page.expect_request(ENTRYPOINT_REQUEST, timeout=REQUEST_TIMEOUT_MS):
            page.goto(OZON_URL)

        user_agent = page.evaluate("() => navigator.userAgent")
        cookies = {c["name"]: c["value"] for c in context.cookies()}

    session = SessionData(cookies=cookies, headers={"user-agent": user_agent})

    if session.is_authenticated:
        logger.info(f"Got authenticated session (user id {cookies[USER_ID_COOKIE]})")
    else:
        logger.warning("Got anonymous session, prices will not match a logged in user")

    return session
