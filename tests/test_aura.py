from kirtap.aura import AURA_MOVES, random_aura_move
from kirtap.cogs.aura import aura_embed


def test_aura_moves_are_unique_and_can_be_selected() -> None:
    names = [move.name for move in AURA_MOVES]

    assert names == [
        "6/7",
        "6/7 au sol",
        "Dab",
        "Dab 360 no scope",
        "Floss",
        "Take the L",
        "High Kick",
        "Moscow Move",
    ]
    assert len(set(names)) == len(names)
    assert random_aura_move() in AURA_MOVES


def test_aura_embed_contains_the_selected_move() -> None:
    move = AURA_MOVES[-1]
    embed = aura_embed(move)

    assert embed.title == "Battle d'aura"
    assert move.name in embed.description
    assert embed.fields[0].value == "+2000"
