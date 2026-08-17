"""One time Ozon login into the persistent Camoufox profile.

Run locally with a display attached, complete the phone + SMS login by hand,
then copy the profile directory to the server:

    uv run python scripts/ozon_login.py
    rsync -a data/ user@server:/root/MarketplacesGoodsTracker/data/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parsing.ozon_session_parser import (  # noqa: E402
    ANONYMOUS_USER_IDS,
    FINGERPRINT_PATH,
    PROFILE_DIR,
    USER_ID_COOKIE,
    open_profile,
)


def main() -> int:
    print(f"Profile:     {PROFILE_DIR.resolve()}")
    print(f"Fingerprint: {FINGERPRINT_PATH.resolve()}")

    with open_profile(headless=False) as context:
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.ozon.ru/")

        print("\nLog in to the tracking account in the opened browser.")
        input("Press Enter once you are logged in...")

        cookies = {c["name"]: c["value"] for c in context.cookies()}

    user_id = cookies.get(USER_ID_COOKIE, "0")
    if user_id in ANONYMOUS_USER_IDS:
        print(f"\nStill anonymous ({USER_ID_COOKIE}={user_id!r}). Login did not stick.")
        return 1

    print(f"\nLogged in as user id {user_id}. Profile saved to {PROFILE_DIR.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
