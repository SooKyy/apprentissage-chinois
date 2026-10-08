from app.models import Card, Sentence, Word


def sentence_out(sentence: Sentence) -> dict:
    return {"id": sentence.id, "zh": sentence.zh, "pinyin": sentence.pinyin, "fr": sentence.fr}


def word_brief(word: Word, status: str | None = None) -> dict:
    return {
        "id": word.id,
        "simp": word.simp,
        "trad": word.trad,
        "pinyin": word.pinyin,
        "gloss_fr": word.llm_fr or word.gloss_fr,
        "gloss_en": word.gloss_en,
        "hsk": word.hsk,
        "freq_rank": word.freq_rank,
        "status": status,
    }


def word_full(word: Word) -> dict:
    data = word_brief(word, word.user.status if word.user else None)
    data.update(
        {
            "readings": word.readings,
            "dict_fr": word.gloss_fr,
            "llm_fr": word.llm_fr,
            "llm_note": word.llm_note,
            "enriched": word.enriched_at is not None,
            "sentences": [sentence_out(s) for s in word.sentences],
        }
    )
    return data


def card_out(card: Card, intervals: dict[str, str]) -> dict:
    return {
        "id": card.id,
        "kind": card.kind,
        "is_new": card.introduced_at is None,
        "state": card.state,
        "reps": card.reps,
        "lapses": card.lapses,
        "intervals": intervals,
        "word": word_full(card.word),
    }
