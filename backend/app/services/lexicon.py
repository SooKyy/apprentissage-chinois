import math

from sqlalchemy.orm import Session

from app.models import Word
from app.services.pinyin import Lexicon

_UNRANKED = 300_000
# Loi de Zipf : P(mot) ~ 1 / (rang x H), d'où coût = ln(rang) + ln(H) ; H ~ 12 pour ce lexique
_PER_WORD = 2.5

_cache: Lexicon | None = None


def get(db: Session) -> Lexicon:
    """Lecture principale et coût de fréquence de chaque mot du dictionnaire, chargés une fois par processus.

    Sert à découper les phrases en mots pour en écrire le pinyin avec les lectures du dictionnaire.
    """
    global _cache
    if _cache is None:
        loaded: Lexicon = {}
        for simp, reading, rank in db.query(Word.simp, Word.pinyin, Word.freq_rank):
            cost = math.log(rank or _UNRANKED) + _PER_WORD
            if len(simp) == 1:
                loaded[simp] = (None, cost)
                continue
            syllables = reading.split()
            if len(syllables) == len(simp):
                loaded[simp] = (syllables, cost)
        _cache = loaded
    return _cache


def reset() -> None:
    global _cache
    _cache = None
