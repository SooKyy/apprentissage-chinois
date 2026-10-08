from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, ReviewLog, UserWord, Word
from app.services import srs
from app.services.clock import day_start, study_day, utcnow

router = APIRouter(prefix="/api/stats", tags=["stats"])

COVERAGE_STEPS = (500, 1000, 2000, 3000, 5000)


@router.get("")
def stats(db: Session = Depends(get_db)) -> dict:
    now = utcnow()
    start = day_start(now)
    today = study_day(now)
    _cards, counts = srs.build_queue(db, now, limit=1)

    by_status = dict(db.query(UserWord.status, func.count()).group_by(UserWord.status))

    since = start - timedelta(days=400)
    days = {study_day(moment) for (moment,) in db.query(ReviewLog.reviewed_at).filter(ReviewLog.reviewed_at >= since)}
    streak = 0
    cursor = today if today in days else today - timedelta(days=1)
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)

    history = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        day_begin = start - timedelta(days=offset)
        total = (
            db.query(func.count(ReviewLog.id))
            .filter(ReviewLog.reviewed_at >= day_begin, ReviewLog.reviewed_at < day_begin + timedelta(days=1))
            .scalar()
        )
        history.append({"day": day.isoformat(), "reviews": total})

    mature = db.query(ReviewLog).filter(
        ReviewLog.reviewed_at >= start - timedelta(days=30), ReviewLog.state_before == 2
    )
    mature_total = mature.count()
    retention = round(mature.filter(ReviewLog.rating > 1).count() / mature_total, 3) if mature_total else None

    coverage = []
    for top in COVERAGE_STEPS:
        base = db.query(Word).filter(Word.freq_rank <= top, Word.is_proper.is_(False))
        per_status = dict(
            base.join(UserWord, UserWord.word_id == Word.id)
            .with_entities(UserWord.status, func.count())
            .group_by(UserWord.status)
        )
        coverage.append(
            {
                "top": top,
                "total": base.count(),
                "known": per_status.get("known", 0),
                "learning": per_status.get("learning", 0),
                "ignored": per_status.get("ignored", 0),
            }
        )

    forecast = []
    active = (
        db.query(Card)
        .join(UserWord, UserWord.word_id == Card.word_id)
        .filter(UserWord.status == "learning", Card.introduced_at.isnot(None))
    )
    for offset in range(1, 8):
        day_begin = start + timedelta(days=offset)
        total = active.filter(Card.due >= day_begin, Card.due < day_begin + timedelta(days=1)).count()
        forecast.append({"day": (today + timedelta(days=offset)).isoformat(), "due": total})

    return {
        "queue": counts,
        "words": {
            "learning": by_status.get("learning", 0),
            "known": by_status.get("known", 0),
            "ignored": by_status.get("ignored", 0),
        },
        "reviews_today": history[-1]["reviews"],
        "streak": streak,
        "retention_30d": retention,
        "history": history,
        "coverage": coverage,
        "forecast": forecast,
    }
