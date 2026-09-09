import asyncio
from datetime import date
from io import BytesIO

from PIL import Image

from kirtap.ade import USER_AGENT, AdeApi, events_for_week, parse_ical_events
from kirtap.ade_image import render_week_schedule, schedule_image_filename

ICALENDAR = b"""BEGIN:VCALENDAR
METHOD:PUBLISH
PRODID:-//ADE/version 6.0
VERSION:2.0
BEGIN:VEVENT
DTSTART:20260909T083000Z
DTEND:20260909T103000Z
SUMMARY:Compilation TD SIRIS ISR RIO
LOCATION:J0a
UID:ade-1
END:VEVENT
BEGIN:VEVENT
DTSTART:20260910T113000Z
DTEND:20260910T143000Z
SUMMARY:Compilation TP RIO
LOCATION:J4
UID:ade-2
END:VEVENT
BEGIN:VEVENT
DTSTART:20261006T133000Z
DTEND:20261006T153000Z
SUMMARY:Cours suivant
LOCATION:J2
UID:ade-3
END:VEVENT
END:VCALENDAR
"""


class FakeResponse:
    def __init__(self, *, status: int, body: bytes) -> None:
        self.status = status
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


def test_ade_icalendar_is_fetched_and_parsed() -> None:
    session = FakeSession(FakeResponse(status=200, body=ICALENDAR))
    api = AdeApi(session, "https://ade.example/calendar.ics")  # type: ignore[arg-type]

    events = asyncio.run(api.fetch_events())

    assert session.url == "https://ade.example/calendar.ics"
    assert session.headers == {
        "Accept": "text/calendar",
        "User-Agent": USER_AGENT,
    }
    assert [
        (event.title, event.starts_at.strftime("%H:%M"), event.location) for event in events
    ] == [
        ("Compilation TD SIRIS ISR RIO", "10:30", "J0a"),
        ("Compilation TP RIO", "13:30", "J4"),
        ("Cours suivant", "15:30", "J2"),
    ]


def test_ade_week_filter_and_schedule_image_show_only_the_current_week() -> None:
    events = parse_ical_events(ICALENDAR)

    current_week = events_for_week(events, reference=date(2026, 9, 9))
    image_data = render_week_schedule(events, reference=date(2026, 9, 9))

    assert [event.identifier for event in current_week] == ["ade-1", "ade-2"]
    assert schedule_image_filename(reference=date(2026, 9, 9)) == "planning-ade-2026-09-07.png"
    with Image.open(BytesIO(image_data)) as image:
        assert image.format == "PNG"
        assert image.width == 1400
        assert image.height > 1000
