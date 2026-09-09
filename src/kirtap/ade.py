import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from icalendar import Calendar

PARIS_TIMEZONE = ZoneInfo("Europe/Paris")
USER_AGENT = "kirtaP/0.2 (+https://github.com/Kylian-Project/kirtaP)"

logger = logging.getLogger(__name__)


class AdeApiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdeEvent:
    identifier: str
    title: str
    starts_at: datetime
    ends_at: datetime
    location: str | None


class AdeApi:
    def __init__(self, session: aiohttp.ClientSession, ical_url: str) -> None:
        self._session = session
        self._ical_url = ical_url

    async def fetch_events(self) -> list[AdeEvent]:
        try:
            async with self._session.get(
                self._ical_url,
                headers={
                    "Accept": "text/calendar",
                    "User-Agent": USER_AGENT,
                },
            ) as response:
                if response.status != 200:
                    raise AdeApiError(f"ADE a répondu avec le statut {response.status}.")
                payload = await response.read()
        except (aiohttp.ClientError, TimeoutError) as error:
            raise AdeApiError("Impossible de joindre ADE.") from error

        if not payload:
            raise AdeApiError("ADE a renvoyé un calendrier vide.")
        return parse_ical_events(payload)


def parse_ical_events(payload: bytes) -> list[AdeEvent]:
    try:
        calendar = Calendar.from_ical(payload)
    except (TypeError, ValueError) as error:
        raise AdeApiError("ADE a renvoyé un calendrier iCalendar invalide.") from error

    events: dict[str, AdeEvent] = {}
    for component in calendar.walk("VEVENT"):
        starts_at = _event_datetime(component, "DTSTART")
        ends_at = _event_datetime(component, "DTEND")
        if starts_at is None or ends_at is None:
            logger.warning("Ignoring ADE event without valid dates")
            continue
        if ends_at <= starts_at:
            logger.warning(
                "Ignoring ADE event with invalid duration: %s", _event_text(component, "UID")
            )
            continue

        title = _event_text(component, "SUMMARY") or "Cours sans titre"
        identifier = _event_text(component, "UID") or f"{title}|{starts_at.isoformat()}"
        events[identifier] = AdeEvent(
            identifier=identifier,
            title=title,
            starts_at=starts_at,
            ends_at=ends_at,
            location=_event_text(component, "LOCATION"),
        )
    return sorted(events.values(), key=lambda event: (event.starts_at, event.ends_at, event.title))


def events_for_week(events: list[AdeEvent], *, reference: date | None = None) -> list[AdeEvent]:
    reference = reference or datetime.now(PARIS_TIMEZONE).date()
    week_start = reference - timedelta(days=reference.weekday())
    week_end = week_start + timedelta(days=7)
    return [event for event in events if week_start <= event.starts_at.date() < week_end]


def _event_datetime(component: object, name: str) -> datetime | None:
    try:
        value = component.decoded(name)  # type: ignore[union-attr]
    except (KeyError, ValueError):
        return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=PARIS_TIMEZONE)
    return value.astimezone(PARIS_TIMEZONE)


def _event_text(component: object, name: str) -> str | None:
    value = component.get(name)  # type: ignore[union-attr]
    if value is None:
        return None
    text = str(value).strip()
    return text or None
