import pytest

from kirtap.crous import categories_for_meal, find_menu, parse_menu_date


def test_parse_menu_date_is_strict() -> None:
    assert parse_menu_date("01-10-2025") == "01-10-2025"

    with pytest.raises(ValueError):
        parse_menu_date("2025-10-01")


def test_find_menu_uses_the_requested_date() -> None:
    menus = [{"date": "30-09-2025"}, {"date": "01-10-2025"}]

    assert find_menu(menus, "01-10-2025") == {"date": "01-10-2025"}


def test_categories_keep_student_food_in_display_order() -> None:
    meal = {
        "categories": [
            {"libelle": "Salle des personnels - Entrées", "ordre": 1},
            {"libelle": "Salle des étudiants - Desserts", "ordre": 6},
            {"libelle": "Cafeteria", "ordre": 0},
            {"libelle": "Salle des étudiants - Plat du jour 2", "ordre": 4},
            {"libelle": "Salle des étudiants - Entrées", "ordre": 1},
        ]
    }

    labels = [category["libelle"] for category in categories_for_meal(meal)]

    assert labels == [
        "Salle des étudiants - Entrées",
        "Salle des étudiants - Plat du jour 2",
        "Salle des étudiants - Desserts",
        "Cafeteria",
    ]
