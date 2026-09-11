from dataclasses import dataclass
from random import choice


@dataclass(frozen=True, slots=True)
class AuraMove:
    name: str
    description: str
    points: int


AURA_MOVES = (
    AuraMove("6/7", "Le classique, sans la moindre hésitation.", 670),
    AuraMove("6/7 au sol", "La version imprévisible du classique.", 1_200),
    AuraMove("6/7 double dab", "La recharge par excellence.", 1_500),
    AuraMove("Dab", "Simple, net, intemporel.", 800),
    AuraMove("Dab 360 no scope", "Le dab avec difficulté maximale.", 1_800),
    AuraMove("Floss", "Le retour technique venu de Fortnite.", 950),
    AuraMove("Take the L", "Le move de célébration qui met fin au débat.", 1_100),
    AuraMove("High Kick", "Une entrée spectaculaire dans la battle.", 1_350),
    AuraMove("Moscow Move", "Le move au sol réservé aux jours de grande confiance.", 2_000),
)


def random_aura_move() -> AuraMove:
    return choice(AURA_MOVES)
