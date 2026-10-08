from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Sentence, UserWord
from app.serializers import sentence_out, word_brief
from app.services import tts
from app.services.pinyin import has_cjk

router = APIRouter(prefix="/api", tags=["media"])


@router.get("/tts")
async def speak(text: str = Query(min_length=1, max_length=tts.MAX_CHARS)) -> FileResponse:
    text = text.strip()
    if not has_cjk(text):
        raise HTTPException(status_code=422, detail="Le texte ne contient pas de chinois")
    try:
        path = await tts.synthesize(text)
    except tts.TTSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=31536000"})


@router.get("/listen")
def listen(limit: int = Query(10, ge=1, le=30), db: Session = Depends(get_db)) -> list[dict]:
    """Phrases tirées au hasard parmi celles de tes mots connus ou en cours, pour la dictée."""
    sentences = (
        db.query(Sentence)
        .options(joinedload(Sentence.word))
        .join(UserWord, UserWord.word_id == Sentence.word_id)
        .filter(UserWord.status.in_(("learning", "known")))
        .order_by(func.random())
        .limit(limit)
        .all()
    )
    return [{**sentence_out(sentence), "word": word_brief(sentence.word)} for sentence in sentences]
