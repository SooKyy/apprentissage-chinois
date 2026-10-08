from datetime import datetime, timedelta

from fsrs import Card as FsrsCard
from fsrs import Rating, Scheduler, State
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.models import Card, ReviewLog, UserWord, Word
from app.services import prefs
from app.services.clock import day_start, to_aware, to_naive

# Une carte en apprentissage due dans moins de 20 min est servie tout de suite s'il ne reste rien d'autre
LEARN_AHEAD = timedelta(minutes=20)
MANUAL_SOURCES = ("dico", "llm")


def scheduler(db: Session, fuzzing: bool = True) -> Scheduler:
    return Scheduler(desired_retention=float(prefs.get(db, "desired_retention")), enable_fuzzing=fuzzing)


def ensure_cards(db: Session, word_id: int, now: datetime) -> None:
    existing = {kind for (kind,) in db.query(Card.kind).filter(Card.word_id == word_id)}
    for kind in prefs.get(db, "card_kinds"):
        if kind not in existing:
            db.add(Card(word_id=word_id, kind=kind, created_at=now))


def set_status(db: Session, word: Word, status: str, source: str, now: datetime) -> UserWord:
    entry = db.get(UserWord, word.id)
    if entry is None:
        entry = UserWord(word_id=word.id, status=status, source=source, created_at=now, updated_at=now)
        db.add(entry)
    else:
        entry.status = status
        entry.updated_at = now
    if status == "learning":
        ensure_cards(db, word.id, now)
    return entry


def clear_status(db: Session, word: Word) -> None:
    """Remet le mot à « non trié ». Les cartes jamais vues sont supprimées, l'historique est conservé."""
    db.query(Card).filter(Card.word_id == word.id, Card.introduced_at.is_(None)).delete()
    entry = db.get(UserWord, word.id)
    if entry is not None:
        db.delete(entry)


def _active(db: Session):
    return (
        db.query(Card)
        .join(UserWord, UserWord.word_id == Card.word_id)
        .filter(UserWord.status == "learning")
    )


def build_queue(db: Session, now: datetime, limit: int = 40) -> tuple[list[Card], dict[str, int]]:
    """File de révision : apprentissage en cours, révisions dues, cartes neuves (dans la limite du jour).

    Deux cartes du même mot ne sont jamais servies ensemble : une carte en révision est repoussée
    si une autre carte du mot a déjà été vue aujourd'hui, et une carte neuve attend le lendemain.
    """
    start = day_start(now)
    options = joinedload(Card.word).joinedload(Word.sentences)

    seen_today = {
        (card_id, word_id)
        for card_id, word_id in db.query(Card.id, Card.word_id).filter(Card.last_review >= start)
    }
    words_today: dict[int, set[int]] = {}
    for card_id, word_id in seen_today:
        words_today.setdefault(word_id, set()).add(card_id)

    queue: list[Card] = []
    used_words: set[int] = set()

    def take(card: Card) -> None:
        queue.append(card)
        used_words.add(card.word_id)

    due = (
        _active(db)
        .options(options)
        .filter(Card.introduced_at.isnot(None), Card.due <= now)
        .order_by(case((Card.state == State.Review.value, 1), else_=0), Card.due)
        .all()
    )
    for card in due:
        if card.state == State.Review.value:
            other_seen = words_today.get(card.word_id, set()) - {card.id}
            if other_seen or card.word_id in used_words:
                continue
        take(card)
    due_count = len(queue)

    introduced_today = (
        db.query(func.count(Card.id)).filter(Card.introduced_at >= start).scalar() or 0
    )
    new_left = max(0, int(prefs.get(db, "new_per_day")) - introduced_today)
    kind_order = case({kind: index for index, kind in enumerate(prefs.KINDS)}, value=Card.kind)
    new_cards = (
        _active(db)
        .options(options)
        .join(Word, Word.id == Card.word_id)
        .filter(Card.introduced_at.is_(None))
        .order_by(
            case((UserWord.source.in_(MANUAL_SOURCES), 0), else_=1),
            case((UserWord.source.in_(MANUAL_SOURCES), UserWord.created_at), else_=None),
            Word.freq_rank.is_(None),
            Word.freq_rank,
            Card.word_id,
            kind_order,
        )
        .all()
    )
    new_available = 0
    new_taken = 0
    for card in new_cards:
        if card.word_id in used_words or card.word_id in words_today:
            continue
        new_available += 1
        if new_taken < new_left:
            take(card)
            new_taken += 1
        else:
            used_words.add(card.word_id)

    if not queue:
        ahead = (
            _active(db)
            .options(options)
            .filter(
                Card.introduced_at.isnot(None),
                Card.state != State.Review.value,
                Card.due > now,
                Card.due <= now + LEARN_AHEAD,
            )
            .order_by(Card.due)
            .all()
        )
        queue.extend(ahead)
        due_count = len(ahead)

    counts = {
        "due": due_count,
        "new": new_taken,
        "new_backlog": new_available,
        "introduced_today": introduced_today,
    }
    return queue[:limit], counts


def _fsrs_card(card: Card, now: datetime) -> FsrsCard:
    if card.introduced_at is None or not card.fsrs:
        return FsrsCard(due=to_aware(now))
    return FsrsCard.from_dict(card.fsrs)


def answer(db: Session, card: Card, rating: int, now: datetime, duration_ms: int | None = None) -> Card:
    snapshot = {
        "fsrs": card.fsrs,
        "state": card.state,
        "due": card.due.isoformat() if card.due else None,
        "introduced_at": card.introduced_at.isoformat() if card.introduced_at else None,
        "last_review": card.last_review.isoformat() if card.last_review else None,
        "reps": card.reps,
        "lapses": card.lapses,
    }
    state_before = card.state if card.introduced_at is not None else None
    updated, _log = scheduler(db).review_card(_fsrs_card(card, now), Rating(rating), review_datetime=to_aware(now))

    card.fsrs = updated.to_dict()
    card.state = updated.state.value
    card.due = to_naive(updated.due)
    card.last_review = now
    card.reps += 1
    if state_before == State.Review.value and rating == Rating.Again.value:
        card.lapses += 1
    if card.introduced_at is None:
        card.introduced_at = now
    db.add(
        ReviewLog(
            card_id=card.id,
            rating=rating,
            state_before=state_before,
            reviewed_at=now,
            duration_ms=duration_ms,
            snapshot=snapshot,
        )
    )
    return card


def undo_last(db: Session) -> Card | None:
    """Annule la toute dernière réponse (erreur de doigt) et rend la carte restaurée."""
    log = db.query(ReviewLog).order_by(ReviewLog.id.desc()).first()
    if log is None or log.snapshot is None:
        return None
    card = db.get(Card, log.card_id)
    snap = log.snapshot
    card.fsrs = snap["fsrs"]
    card.state = snap["state"]
    card.due = datetime.fromisoformat(snap["due"]) if snap["due"] else None
    card.introduced_at = datetime.fromisoformat(snap["introduced_at"]) if snap["introduced_at"] else None
    card.last_review = datetime.fromisoformat(snap["last_review"]) if snap["last_review"] else None
    card.reps = snap["reps"]
    card.lapses = snap["lapses"]
    db.delete(log)
    return card


def format_interval(delta: timedelta) -> str:
    minutes = delta.total_seconds() / 60
    if minutes < 60:
        return f"{max(1, round(minutes))} min"
    hours = minutes / 60
    if hours < 24:
        return f"{round(hours)} h"
    days = hours / 24
    if days < 30:
        return f"{round(days)} j"
    if days < 365:
        return f"{round(days / 30)} mois"
    years = days / 365
    return f"{years:.1f}".rstrip("0").rstrip(".") + (" an" if years < 2 else " ans")


def preview(db: Session, card: Card, now: datetime) -> dict[str, str]:
    """Prochain intervalle pour chaque note, affiché sur les boutons de réponse."""
    plain = scheduler(db, fuzzing=False)
    base = _fsrs_card(card, now)
    aware = to_aware(now)
    out: dict[str, str] = {}
    for rating in Rating:
        simulated, _ = plain.review_card(FsrsCard.from_dict(base.to_dict()), rating, review_datetime=aware)
        out[str(rating.value)] = format_interval(simulated.due - aware)
    return out
