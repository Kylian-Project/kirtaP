import asyncio
from datetime import date

import pytest

from kirtap.crous import (
    USER_AGENT,
    CrousApi,
    format_menu_date,
    menu_image_filename,
    next_menu_dates,
    parse_menu_date,
)


class FakeResponse:
    def __init__(self, *, status: int, body: bytes = b"") -> None:
        self.status = status
        self.headers: dict[str, str] = {}
        self._body = body

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def read(self) -> bytes:
        return self._body


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.url = ""
        self.headers: dict[str, str] = {}

    def get(self, url: str, *, headers: dict[str, str]) -> FakeResponse:
        self.url = url
        self.headers = headers
        return self.response


def test_parse_menu_date_is_strict() -> None:
    assert parse_menu_date("01-10-2025") == "01-10-2025"

    with pytest.raises(ValueError):
        parse_menu_date("2025-10-01")


def test_menu_date_is_formatted_in_french() -> None:
    assert format_menu_date("03-09-2026") == "jeudi 3 septembre"
    assert menu_image_filename("03-09-2026") == "menu-crous-03-09-2026.png"


def test_menu_dates_show_the_next_five_weekdays() -> None:
    dates = ["04-09-2026", "05-09-2026", "07-09-2026", "08-09-2026", "09-09-2026", "10-09-2026"]

    assert next_menu_dates(dates, reference=date(2026, 9, 4)) == [
        "04-09-2026",
        "07-09-2026",
        "08-09-2026",
        "09-09-2026",
        "10-09-2026",
    ]


def test_menu_image_request_uses_the_official_endpoint_and_custom_user_agent() -> None:
    session = FakeSession(FakeResponse(status=200, body=b"PNG"))
    api = CrousApi(session, 1392)  # type: ignore[arg-type]

    assert asyncio.run(api.fetch_menu_image("03-09-2026")) == b"PNG"
    assert session.url == "https://api.croustillant.menu/v1/restaurants/1392/menu/03-09-2026/image"
    assert session.headers == {"Accept": "image/png", "User-Agent": USER_AGENT}
