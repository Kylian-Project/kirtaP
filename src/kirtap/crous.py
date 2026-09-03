import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp

API_BASE_URL = "https://api.croustillant.menu/v1"
USER_AGENT = "kirtaP/0.1 (+https://github.com/Kylian-Project/kirtaP)"
PARIS_TIMEZONE = ZoneInfo("Europe/Paris")
logger = logging.getLogger(__name__)


class CrousApiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Restaurant:
    name: str


class CrousApi:
    def __init__(self, session: aiohttp.ClientSession, restaurant_id: int) -> None:
        self._session = session
        self._restaurant_id = restaurant_id

    async def fetch_menu_image(self, menu_date: str) -> bytes | None:
        url = f"{self._restaurant_url}/menu/{menu_date}/image"
        try:
            async with self._session.get(
                url, headers=self._headers(accept="image/png")
            ) as response:
                if response.status == 404:
                    logger.info("No CROUS menu image is available for %s", menu_date)
                    return None
                if response.status != 200:
                    await self._raise_for_response("menu image", response)

                image = await response.read()
        except (aiohttp.ClientError, TimeoutError) as error:
            raise CrousApiError("Impossible de joindre CROUStillant.") from error

        if not image:
            raise CrousApiError("CROUStillant a renvoyé une image vide.")
        return image

    async def fetch_restaurant(self) -> Restaurant:
        data = await self._fetch_json(self._restaurant_url, "restaurant")
        if not isinstance(data, Mapping):
            raise CrousApiError("CROUStillant a renvoyé un restaurant invalide.")

        name = data.get("nom")
        if not isinstance(name, str) or not name.strip():
            raise CrousApiError("CROUStillant n'a pas renvoyé le nom du restaurant.")
        return Restaurant(name=name.strip())

    async def fetch_is_open(self) -> bool:
        data = await self._fetch_json(
            f"{API_BASE_URL}/restaurants/status/minimal", "restaurant status"
        )
        if not isinstance(data, list):
            raise CrousApiError("CROUStillant a renvoyé un statut de restaurant invalide.")

        for status in data:
            if not isinstance(status, Mapping) or status.get("code") != self._restaurant_id:
                continue
            is_open = status.get("ouvert")
            if isinstance(is_open, bool):
                return is_open

        raise CrousApiError("CROUStillant n'a pas renvoyé le statut du restaurant configuré.")

    async def fetch_menu_dates(self) -> list[str]:
        data = await self._fetch_json(f"{self._restaurant_url}/menu/dates/all", "menu dates")
        if not isinstance(data, list):
            raise CrousApiError("CROUStillant a renvoyé une liste de dates invalide.")

        dates: list[str] = []
        for item in data:
            if not isinstance(item, Mapping) or not isinstance(value := item.get("date"), str):
                continue
            try:
                dates.append(parse_menu_date(value))
            except ValueError:
                logger.warning("Ignoring invalid CROUS menu date: %r", value)

        return sorted(set(dates), key=_to_date)

    @property
    def _restaurant_url(self) -> str:
        return f"{API_BASE_URL}/restaurants/{self._restaurant_id}"

    @staticmethod
    def _headers(*, accept: str = "application/json") -> dict[str, str]:
        return {"Accept": accept, "User-Agent": USER_AGENT}

    async def _fetch_json(self, url: str, resource: str) -> object:
        try:
            async with self._session.get(url, headers=self._headers()) as response:
                if response.status != 200:
                    await self._raise_for_response(resource, response)
                payload = await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as error:
            raise CrousApiError("Impossible de récupérer les données CROUStillant.") from error

        if not isinstance(payload, Mapping) or payload.get("success") is not True:
            raise CrousApiError("CROUStillant a renvoyé une réponse invalide.")
        return payload.get("data")

    async def _raise_for_response(self, resource: str, response: aiohttp.ClientResponse) -> None:
        request_id = response.headers.get("x-request-id") or response.headers.get("cf-ray")
        logger.warning(
            "CROUS API %s request failed with status %s%s",
            resource,
            response.status,
            f" (request {request_id})" if request_id else "",
        )
        raise CrousApiError(f"CROUStillant a répondu avec le statut {response.status}.")


def parse_menu_date(value: str) -> str:
    return _to_date(value).strftime("%d-%m-%Y")


def today_menu_date() -> str:
    return datetime.now(PARIS_TIMEZONE).strftime("%d-%m-%Y")


def format_menu_date(value: str) -> str:
    menu_date = _to_date(value)
    weekdays = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
    months = (
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    )
    return f"{weekdays[menu_date.weekday()]} {menu_date.day} {months[menu_date.month - 1]}"


def next_menu_dates(values: Sequence[str], *, reference: date | None = None) -> list[str]:
    reference = reference or datetime.now(PARIS_TIMEZONE).date()
    weekdays: list[date] = []
    candidate = reference
    while len(weekdays) < 5:
        if candidate.weekday() < 5:
            weekdays.append(candidate)
        candidate += timedelta(days=1)

    available_dates = {_to_date(value): value for value in values}
    return [available_dates[menu_date] for menu_date in weekdays if menu_date in available_dates]


def menu_image_filename(menu_date: str) -> str:
    return f"menu-crous-{parse_menu_date(menu_date)}.png"


def _to_date(value: str) -> date:
    return datetime.strptime(value, "%d-%m-%Y").date()
