import logging
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

PARIS_TIMEZONE = ZoneInfo("Europe/Paris")
logger = logging.getLogger(__name__)

Menu = dict[str, Any]
Category = Mapping[str, Any]


class CrousApi:
    def __init__(self, session: aiohttp.ClientSession, restaurant_id: int) -> None:
        self._session = session
        self._url = f"https://api.croustillant.menu/v1/restaurants/{restaurant_id}/menu"

    async def fetch_menus(self) -> list[Menu] | None:
        try:
            async with self._session.get(self._url) as response:
                if response.status != 200:
                    logger.warning("CROUS API responded with status %s", response.status)
                    return None
                payload = await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            logger.exception("Unable to fetch CROUS menus")
            return None

        if not isinstance(payload, dict) or payload.get("success") is not True:
            logger.warning("CROUS API returned an unsuccessful response")
            return None

        data = payload.get("data")
        if not isinstance(data, list):
            logger.warning("CROUS API returned an invalid menu list")
            return None

        return [menu for menu in data if isinstance(menu, dict)]


def parse_menu_date(value: str) -> str:
    if len(value) != 10:
        raise ValueError(value)
    return datetime.strptime(value, "%d-%m-%Y").strftime("%d-%m-%Y")


def today_menu_date() -> str:
    return datetime.now(PARIS_TIMEZONE).strftime("%d-%m-%Y")


def find_menu(menus: Sequence[Menu], target_date: str) -> Menu | None:
    return next((menu for menu in menus if menu.get("date") == target_date), None)


def menu_meals(menu: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    meals = menu.get("repas")
    if not isinstance(meals, list):
        return []
    return [meal for meal in meals if isinstance(meal, dict)]


def categories_for_meal(meal: Mapping[str, Any]) -> list[Category]:
    categories = meal.get("categories")
    if not isinstance(categories, list):
        return []

    students: list[Category] = []
    cafeterias: list[Category] = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        label = _normalise(category.get("libelle", ""))
        if "personnel" in label:
            continue
        if "etudiant" in label:
            students.append(category)
        elif "cafeteria" in label:
            cafeterias.append(category)

    return sorted(students, key=_category_sort_key) + sorted(cafeterias, key=_category_sort_key)


def category_dishes(category: Category) -> list[str]:
    dishes = category.get("plats")
    if not isinstance(dishes, list):
        return []
    return [
        str(dish["libelle"]) for dish in dishes if isinstance(dish, dict) and dish.get("libelle")
    ]


def _category_sort_key(category: Category) -> tuple[int, int, str]:
    label = _normalise(category.get("libelle", ""))
    priorities = ("entree", "barbecue", "plat du jour 1", "plat du jour 2", "pate", "dessert")
    priority = next(
        (index for index, item in enumerate(priorities) if item in label), len(priorities)
    )
    order = category.get("ordre")
    api_order = order if isinstance(order, int) else 999
    return priority, api_order, label


def _normalise(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value).casefold())
    return "".join(character for character in text if not unicodedata.combining(character))
