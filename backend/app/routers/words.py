from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import UserWord, Word, WordPinyin
from app.schemas import StatusRequest
from app.serializers import word_brief, word_full
from app.services import assist, llm, srs
from app.services import pinyin as py
from app.services.clock import utcnow

router = APIRouter(prefix="/api/words", tags=["words"])


def _like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _by_frequency(query):
    return query.order_by(Word.freq_rank.is_(None), Word.freq_rank, Word.id)


def _get_word(db: Session, word_id: int) -> Word:
    word = db.get(Word, word_id)
    if word is None:
        raise HTTPException(status_code=404, detail="Mot introuvable")
    return word


def _search_hanzi(db: Session, q: str, limit: int) -> list[Word]:
    exact = db.query(Word).filter(or_(Word.simp == q, Word.trad == q)).all()
    prefix = _by_frequency(
        db.query(Word).filter(Word.simp.like(_like(q) + "_%", escape="\\"))
    ).limit(limit).all()
    inside = _by_frequency(
        db.query(Word).filter(Word.simp.like("%_" + _like(q) + "%", escape="\\"))
    ).limit(limit).all()
    return exact + prefix + inside


def _search_latin(db: Session, q: str, limit: int) -> list[Word]:
    results: list[Word] = []
    key = py.plain(q)
    if key:
        match = WordPinyin.plain == key
        if "v" not in key:  # « nu » doit aussi trouver « nü »
            match = or_(match, func.replace(WordPinyin.plain, "v", "u") == key)
        ids = db.query(WordPinyin.word_id).filter(match)
        results += _by_frequency(db.query(Word).filter(Word.id.in_(ids))).limit(limit).all()

    needle = q.lower()
    pattern = "%" + _like(needle) + "%"
    by_meaning = _by_frequency(
        db.query(Word).filter(
            or_(
                func.lower(Word.gloss_fr).like(pattern, escape="\\"),
                func.lower(Word.llm_fr).like(pattern, escape="\\"),
                func.lower(Word.gloss_en).like(pattern, escape="\\"),
            )
        )
    ).limit(300).all()

    def is_exact_sense(word: Word) -> bool:
        senses = f"{word.llm_fr or ''};{word.gloss_fr or ''};{word.gloss_en}".lower().split(";")
        return any(sense.strip().removeprefix("to ") == needle for sense in senses)

    # Un sens exactement égal à la recherche (« manger ») passe avant une simple mention
    by_meaning.sort(key=lambda word: not is_exact_sense(word))
    results += by_meaning[:limit]

    if key and len(key) >= 2:
        ids = db.query(WordPinyin.word_id).filter(WordPinyin.plain.like(_like(key) + "_%", escape="\\"))
        results += _by_frequency(db.query(Word).filter(Word.id.in_(ids))).limit(limit).all()
    return results


@router.get("/search")
def search(q: str = Query(min_length=1, max_length=64), limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)) -> list[dict]:
    q = q.strip()
    if not q:
        return []
    found = _search_hanzi(db, q, limit) if py.has_cjk(q) else _search_latin(db, q, limit)
    unique: dict[int, Word] = {}
    for word in found:
        unique.setdefault(word.id, word)
    words = list(unique.values())[:limit]
    statuses = dict(
        db.query(UserWord.word_id, UserWord.status).filter(UserWord.word_id.in_([w.id for w in words]))
    )
    return [word_brief(word, statuses.get(word.id)) for word in words]


@router.get("/mine")
def mine(
    status: str = Query("learning", pattern="^(learning|known|ignored)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    base = db.query(Word).join(UserWord, UserWord.word_id == Word.id).filter(UserWord.status == status)
    words = base.order_by(UserWord.updated_at.desc(), Word.id).offset(offset).limit(limit).all()
    return {"total": base.count(), "words": [word_brief(word, status) for word in words]}


@router.get("/{word_id}")
def detail(word_id: int, db: Session = Depends(get_db)) -> dict:
    word = (
        db.query(Word).options(joinedload(Word.sentences), joinedload(Word.user)).filter(Word.id == word_id).first()
    )
    if word is None:
        raise HTTPException(status_code=404, detail="Mot introuvable")
    return word_full(word)


@router.put("/{word_id}/status")
def set_status(word_id: int, payload: StatusRequest, db: Session = Depends(get_db)) -> dict:
    word = _get_word(db, word_id)
    srs.set_status(db, word, payload.status, payload.source, utcnow())
    db.commit()
    return word_brief(word, payload.status)


@router.delete("/{word_id}/status")
def clear_status(word_id: int, db: Session = Depends(get_db)) -> dict:
    word = _get_word(db, word_id)
    srs.clear_status(db, word)
    db.commit()
    return word_brief(word, None)


@router.post("/{word_id}/enrich")
def enrich(word_id: int, force: bool = False, db: Session = Depends(get_db)) -> dict:
    word = _get_word(db, word_id)
    try:
        assist.enrich_word(db, word, force=force)
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return word_full(word)
