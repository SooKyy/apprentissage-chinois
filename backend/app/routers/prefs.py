from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import prefs

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def read(db: Session = Depends(get_db)) -> dict:
    return prefs.get_all(db)


@router.put("")
def write(changes: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    try:
        return prefs.update(db, changes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
