from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, UserWord
from app.schemas import AnswerRequest
from app.serializers import card_out
from app.services import srs
from app.services.clock import utcnow

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/queue")
def queue(db: Session = Depends(get_db)) -> dict:
    now = utcnow()
    cards, counts = srs.build_queue(db, now)
    return {"counts": counts, "cards": [card_out(card, srs.preview(db, card, now)) for card in cards]}


@router.post("/undo")
def undo(db: Session = Depends(get_db)) -> dict:
    card = srs.undo_last(db)
    if card is None:
        raise HTTPException(status_code=404, detail="Aucune réponse à annuler")
    db.commit()
    db.refresh(card)
    return card_out(card, srs.preview(db, card, utcnow()))


@router.post("/{card_id}")
def answer(card_id: int, payload: AnswerRequest, db: Session = Depends(get_db)) -> dict:
    card = db.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Carte introuvable")
    entry = db.get(UserWord, card.word_id)
    if entry is None or entry.status != "learning":
        raise HTTPException(status_code=409, detail="Ce mot n'est plus en apprentissage")
    now = utcnow()
    srs.answer(db, card, payload.rating, now, payload.duration_ms)
    db.commit()
    return {"id": card.id, "state": card.state, "due_in": srs.format_interval(card.due - now)}
