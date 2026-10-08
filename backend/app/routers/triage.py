from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserWord, Word
from app.schemas import PlacementRequest
from app.serializers import word_brief
from app.services import srs
from app.services.clock import utcnow

router = APIRouter(prefix="/api", tags=["triage"])

# Tranches de rang de fréquence échantillonnées par le test de niveau
BANDS = [(1, 250), (251, 500), (501, 1000), (1001, 1500), (1501, 2000), (2001, 3000),
         (3001, 4000), (4001, 5000), (5001, 7000), (7001, 10000)]
PER_BAND = 12


def _common(db: Session):
    """Mots du lexique courant : classés par fréquence, hors noms propres."""
    return db.query(Word).filter(Word.freq_rank.isnot(None), Word.is_proper.is_(False))


@router.get("/triage")
def triage(
    after_rank: int = Query(0, ge=0),
    hsk: int | None = Query(None, ge=1, le=7),
    limit: int = Query(40, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Prochains mots jamais triés, du plus fréquent au plus rare."""
    untriaged = (
        _common(db)
        .outerjoin(UserWord, UserWord.word_id == Word.id)
        .filter(UserWord.word_id.is_(None), Word.freq_rank > after_rank)
    )
    if hsk is not None:
        untriaged = untriaged.filter(Word.hsk == hsk)
    words = untriaged.order_by(Word.freq_rank).limit(limit).all()
    return {"remaining": untriaged.count(), "words": [word_brief(word) for word in words]}


@router.get("/placement")
def placement_sample(db: Session = Depends(get_db)) -> list[dict]:
    sample: list[dict] = []
    for low, high in BANDS:
        words = (
            _common(db).filter(Word.freq_rank.between(low, high)).order_by(func.random()).limit(PER_BAND).all()
        )
        sample += [word_brief(word) for word in words]
    return sample


@router.post("/placement")
def placement_result(payload: PlacementRequest, db: Session = Depends(get_db)) -> dict:
    answers = {answer.word_id: answer.known for answer in payload.answers}
    words = db.query(Word).filter(Word.id.in_(answers)).all()
    now = utcnow()
    bands = []
    estimate = 0.0
    suggested = None
    for low, high in BANDS:
        tested = [word for word in words if word.freq_rank is not None and low <= word.freq_rank <= high]
        if not tested:
            continue
        known = sum(1 for word in tested if answers[word.id])
        size = _common(db).filter(Word.freq_rank.between(low, high)).count()
        ratio = known / len(tested)
        estimate += ratio * size
        if suggested is None and ratio < 0.8:
            suggested = low - 1
        bands.append({"from": low, "to": high, "tested": len(tested), "known": known, "ratio": round(ratio, 2)})
    for word in words:
        # Un mot déjà trié garde son statut ; seul un « je connais » sur un mot vierge est enregistré
        if answers[word.id] and db.get(UserWord, word.id) is None:
            srs.set_status(db, word, "known", "placement", now)
    db.commit()
    return {
        "estimate": int(round(estimate, -1)),
        "out_of": _common(db).filter(Word.freq_rank <= BANDS[-1][1]).count(),
        "bands": bands,
        "suggested_after_rank": suggested if suggested is not None else BANDS[-1][1],
    }
