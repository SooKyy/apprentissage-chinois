from datetime import datetime, timedelta

from app.models import Card, ReviewLog
from app.services import prefs, srs
from app.services.clock import day_start, study_day

from .conftest import NOW


def learn(db, word, *simps, source="tri", now=NOW):
    for simp in simps:
        srs.set_status(db, word(simp), "learning", source, now)
    db.commit()


def kinds(cards):
    return [(card.word.simp, card.kind) for card in cards]


def test_day_rolls_over_at_4am_paris_time():
    before = datetime(2026, 10, 7, 1, 30)  # 03:30 à Paris
    after = datetime(2026, 10, 7, 2, 30)  # 04:30 à Paris
    assert study_day(before).isoformat() == "2026-10-06"
    assert study_day(after).isoformat() == "2026-10-07"
    assert day_start(after) == datetime(2026, 10, 7, 2, 0)
    assert day_start(before) == datetime(2026, 10, 6, 2, 0)


def test_learning_a_word_creates_one_card_per_enabled_kind(db, word):
    learn(db, word, "吃")
    assert sorted(card.kind for card in db.query(Card)) == ["ecoute", "reco"]
    learn(db, word, "吃")  # idempotent
    assert db.query(Card).count() == 2


def test_new_cards_follow_frequency_and_never_show_two_cards_of_a_word(db, word):
    learn(db, word, "喜欢", "吃", "东西")
    cards, counts = srs.build_queue(db, NOW)
    assert kinds(cards) == [("吃", "reco"), ("东西", "reco"), ("喜欢", "reco")]
    assert counts == {"due": 0, "new": 3, "new_backlog": 3, "introduced_today": 0}


def test_words_added_by_hand_come_before_the_frequency_backlog(db, word):
    learn(db, word, "吃")
    learn(db, word, "难吃", source="dico", now=NOW + timedelta(minutes=1))
    cards, _ = srs.build_queue(db, NOW + timedelta(minutes=2))
    assert kinds(cards) == [("难吃", "reco"), ("吃", "reco")]


def test_daily_new_limit_counts_cards_introduced_today(db, word):
    prefs.update(db, {"new_per_day": 2})
    learn(db, word, "吃", "东西", "喜欢")
    cards, counts = srs.build_queue(db, NOW)
    assert len(cards) == 2 and counts["new_backlog"] == 3
    srs.answer(db, cards[0], 3, NOW)
    db.commit()
    cards, counts = srs.build_queue(db, NOW + timedelta(seconds=5))
    assert counts["introduced_today"] == 1 and counts["new"] == 1
    assert kinds(cards) == [("东西", "reco")]  # la carte de 吃 est en apprentissage, due dans 1 min


def test_learning_steps_then_graduation(db, word):
    learn(db, word, "吃")
    card = srs.build_queue(db, NOW)[0][0]
    srs.answer(db, card, 3, NOW)
    assert card.state == 1 and card.due == NOW + timedelta(minutes=10)
    assert card.introduced_at == NOW and card.reps == 1
    srs.answer(db, card, 3, card.due)
    db.commit()
    assert card.state == 2 and card.due - card.last_review >= timedelta(days=1)


def test_learning_card_is_served_ahead_when_nothing_else_is_left(db, word):
    prefs.update(db, {"card_kinds": ["reco"]})
    learn(db, word, "吃")
    card = srs.build_queue(db, NOW)[0][0]
    srs.answer(db, card, 3, NOW)
    db.commit()
    cards, counts = srs.build_queue(db, NOW + timedelta(minutes=1))
    assert kinds(cards) == [("吃", "reco")] and counts["due"] == 1
    # Au-delà de la fenêtre d'anticipation (due dans 25 min), on ne sert rien
    assert srs.build_queue(db, card.due - timedelta(minutes=25))[0] == []


def test_sibling_card_waits_for_the_next_day(db, word):
    learn(db, word, "吃")
    reco = srs.build_queue(db, NOW)[0][0]
    srs.answer(db, reco, 4, NOW)  # Facile : passe directement en révision
    db.commit()
    assert reco.state == 2
    assert srs.build_queue(db, NOW + timedelta(hours=1))[0] == []
    tomorrow = NOW + timedelta(days=1)
    assert kinds(srs.build_queue(db, tomorrow)[0]) == [("吃", "ecoute")]


def test_due_review_is_postponed_if_its_sibling_was_seen_today(db, word):
    learn(db, word, "吃")
    reco = db.query(Card).filter(Card.kind == "reco").one()
    ecoute = db.query(Card).filter(Card.kind == "ecoute").one()
    srs.answer(db, reco, 4, NOW - timedelta(days=30))
    srs.answer(db, ecoute, 4, NOW - timedelta(days=29))
    db.commit()
    assert reco.due <= NOW and ecoute.due <= NOW
    first = srs.build_queue(db, NOW)[0]
    assert len(first) == 1
    srs.answer(db, first[0], 3, NOW)
    db.commit()
    assert srs.build_queue(db, NOW + timedelta(minutes=5))[0] == []


def test_lapse_is_counted_only_from_review_state(db, word):
    learn(db, word, "吃")
    card = db.query(Card).filter(Card.kind == "reco").one()
    srs.answer(db, card, 1, NOW)
    assert card.lapses == 0
    srs.answer(db, card, 4, NOW + timedelta(minutes=1))
    assert card.state == 2
    srs.answer(db, card, 1, card.due)
    assert card.lapses == 1 and card.state == 3


def test_undo_restores_the_card_exactly(db, word):
    learn(db, word, "吃")
    card = db.query(Card).filter(Card.kind == "reco").one()
    srs.answer(db, card, 3, NOW)
    db.commit()
    before = (dict(card.fsrs), card.state, card.due, card.reps, card.last_review)
    srs.answer(db, card, 1, NOW + timedelta(minutes=10))
    db.commit()
    assert srs.undo_last(db).id == card.id
    db.commit()
    db.refresh(card)
    assert (card.fsrs, card.state, card.due, card.reps, card.last_review) == before
    assert db.query(ReviewLog).count() == 1
    srs.undo_last(db)
    db.commit()
    db.refresh(card)
    assert card.introduced_at is None and card.reps == 0 and card.due is None
    assert srs.undo_last(db) is None


def test_known_or_ignored_words_leave_the_queue_and_clear_keeps_history(db, word):
    learn(db, word, "吃", "东西")
    card = db.query(Card).filter(Card.word_id == word("吃").id, Card.kind == "reco").one()
    srs.answer(db, card, 3, NOW)
    srs.set_status(db, word("吃"), "known", "tri", NOW)
    srs.clear_status(db, word("东西"))
    db.commit()
    assert srs.build_queue(db, NOW + timedelta(hours=1))[0] == []
    assert db.query(Card).filter(Card.word_id == word("东西").id).count() == 0
    srs.clear_status(db, word("吃"))
    db.commit()
    assert [c.kind for c in db.query(Card).filter(Card.word_id == word("吃").id)] == ["reco"]


def test_preview_matches_what_the_buttons_will_do(db, word):
    learn(db, word, "吃")
    card = db.query(Card).filter(Card.kind == "reco").one()
    assert srs.preview(db, card, NOW) == {"1": "1 min", "2": "6 min", "3": "10 min", "4": "8 j"}


def test_format_interval():
    cases = {
        timedelta(seconds=20): "1 min", timedelta(minutes=10): "10 min", timedelta(hours=5): "5 h",
        timedelta(days=3): "3 j", timedelta(days=61): "2 mois", timedelta(days=365): "1 an",
        timedelta(days=912): "2.5 ans",
    }
    for delta, text in cases.items():
        assert srs.format_interval(delta) == text
