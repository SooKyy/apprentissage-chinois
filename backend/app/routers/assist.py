from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CorrectRequest, TextRequest
from app.services import assist, llm

router = APIRouter(prefix="/api/assist", tags=["assist"])


@router.post("/explain")
def explain(payload: TextRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return assist.explain(db, payload.text.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/correct")
def correct(payload: CorrectRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return assist.correct(db, payload.text.strip(), payload.intention)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except llm.LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
