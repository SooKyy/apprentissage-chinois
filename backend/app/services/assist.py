import threading

from sqlalchemy.orm import Session

from app.models import Sentence, Word
from app.services import lexicon, llm
from app.services.clock import utcnow
from app.services.pinyin import has_cjk, sentence_pinyin

_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()

ENRICH_SYSTEM = """Tu es un professeur de mandarin pour un francophone. Tu réponds uniquement par un objet JSON.
On te donne un mot chinois (simplifié), sa lecture et ses sens en anglais. Renvoie :
{"fr": "<sens principaux en français, 1 à 3 sens courts séparés par « ; », du plus courant au plus rare>",
 "note": "<une phrase en français sur l'usage ou une confusion fréquente, ou chaîne vide si rien d'utile>",
 "phrases": [{"zh": "<phrase>", "fr": "<traduction française naturelle>"}, ...]}
Règles pour les 3 phrases :
- chinois simplifié, registre oral quotidien (comme un message entre proches), 5 à 14 caractères ;
- chaque phrase contient le mot EXACTEMENT tel qu'il est écrit, dans son sens le plus courant ;
- hormis le mot étudié, n'utilise que du vocabulaire très fréquent ;
- trois contextes différents ; pas de pinyin, pas de guillemets inutiles."""

EXPLAIN_SYSTEM = """Tu es un professeur de mandarin pour un francophone de niveau intermédiaire. Tu réponds uniquement par un objet JSON.
On te donne un texte en chinois. Renvoie :
{"traduction": "<traduction française naturelle>",
 "litteral": "<traduction mot à mot, pour voir la structure>",
 "mots": [{"zh": "<mot en simplifié, tel qu'au dictionnaire>", "sens": "<sens en français DANS cette phrase>"}, ...],
 "grammaire": [{"point": "<structure, en chinois>", "explication": "<explication française courte, avec ce que ça change au sens>"}, ...],
 "registre": "<ton/registre en une courte phrase : familier, tendre, agacé, neutre…>"}
"mots" suit l'ordre du texte et couvre tous les mots porteurs de sens, particules comprises (了, 吧, 呢…). Pas de pinyin.
"grammaire" ne liste que ce qui est réellement présent (0 à 4 points)."""

CORRECT_SYSTEM = """Tu es un professeur de mandarin, locuteur natif, pour un francophone de niveau intermédiaire. Tu réponds uniquement par un objet JSON.
On te donne un message qu'il veut envoyer en chinois, et parfois ce qu'il veut dire en français. Renvoie :
{"correct": <true si le message est déjà correct et naturel, sinon false>,
 "corrige": "<version corrigée, en restant au plus près de ses mots ; identique à l'original s'il est correct>",
 "naturel": "<comment un natif le dirait à l'oral entre proches, en simplifié ; peut être identique à corrige>",
 "traduction": "<traduction française de la version corrigée>",
 "erreurs": [{"original": "<passage fautif>", "correction": "<passage corrigé>", "explication": "<pourquoi, en français, court>"}, ...]}
"erreurs" est vide si rien n'est faux. Ne signale pas comme erreur un simple choix de style. Pas de pinyin."""


def _lock_for(word_id: int) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(word_id, threading.Lock())


def _text(value: object, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def enrich_word(db: Session, word: Word, force: bool = False) -> Word:
    """Ajoute au mot un sens français court et des phrases d'exemple générés par le LLM (une seule fois)."""
    with _lock_for(word.id):
        db.refresh(word)
        if word.enriched_at is not None and not force:
            return word
        readings = "\n".join(
            f"- {reading['pinyin']} : {'; '.join(reading['en'][:6])}" for reading in word.readings[:4]
        )
        data = llm.chat_json(
            ENRICH_SYSTEM, f"Mot : {word.simp}\nLectures et sens :\n{readings}", max_tokens=700
        )
        fr = _text(data.get("fr"), 200)
        if not fr:
            raise llm.LLMError("Réponse du modèle sans sens français")
        seen = {sentence.zh for sentence in word.sentences}
        now = utcnow()
        for item in data.get("phrases") or []:
            if not isinstance(item, dict):
                continue
            zh, translation = _text(item.get("zh"), 80), _text(item.get("fr"), 200)
            # Garde-fou : une phrase qui ne contient pas le mot ne sert à rien pour la carte
            if not zh or not translation or word.simp not in zh or zh in seen:
                continue
            seen.add(zh)
            db.add(
                Sentence(
                    word_id=word.id, zh=zh, pinyin=sentence_pinyin(zh, lexicon.get(db)), fr=translation,
                    created_at=now,
                )
            )
        word.llm_fr = fr
        word.llm_note = _text(data.get("note"), 300) or None
        word.enriched_at = now
        db.commit()
        db.refresh(word)
        return word


def explain(db: Session, text: str) -> dict:
    if not has_cjk(text):
        raise ValueError("Le texte ne contient pas de chinois")
    data = llm.chat_json(EXPLAIN_SYSTEM, text, max_tokens=2500)
    words = []
    for item in data.get("mots") or []:
        if not isinstance(item, dict):
            continue
        zh, sense = _text(item.get("zh"), 32), _text(item.get("sens"), 200)
        if not zh or not has_cjk(zh):
            continue
        entry = db.query(Word).filter(Word.simp == zh).first()
        words.append(
            {
                "zh": zh,
                "sens": sense,
                "pinyin": entry.pinyin if entry else sentence_pinyin(zh, lexicon.get(db)),
                "word_id": entry.id if entry else None,
                "status": entry.user.status if entry and entry.user else None,
            }
        )
    grammar = [
        {"point": _text(item.get("point"), 80), "explication": _text(item.get("explication"), 400)}
        for item in data.get("grammaire") or []
        if isinstance(item, dict) and _text(item.get("point"), 80)
    ]
    return {
        "texte": text,
        "pinyin": sentence_pinyin(text, lexicon.get(db)),
        "traduction": _text(data.get("traduction"), 800),
        "litteral": _text(data.get("litteral"), 800),
        "mots": words,
        "grammaire": grammar,
        "registre": _text(data.get("registre"), 200),
    }


def correct(db: Session, text: str, intention: str) -> dict:
    if not has_cjk(text):
        raise ValueError("Le texte ne contient pas de chinois")
    prompt = f"Message : {text}"
    if intention.strip():
        prompt += f"\nCe qu'il veut dire : {intention.strip()}"
    data = llm.chat_json(CORRECT_SYSTEM, prompt, max_tokens=2500)
    fixed = _text(data.get("corrige"), 800) or text
    natural = _text(data.get("naturel"), 800) or fixed
    errors = [
        {
            "original": _text(item.get("original"), 200),
            "correction": _text(item.get("correction"), 200),
            "explication": _text(item.get("explication"), 400),
        }
        for item in data.get("erreurs") or []
        if isinstance(item, dict) and _text(item.get("explication"), 400)
    ]
    return {
        "original": text,
        "correct": bool(data.get("correct")) and not errors,
        "corrige": fixed,
        "corrige_pinyin": sentence_pinyin(fixed, lexicon.get(db)),
        "naturel": natural,
        "naturel_pinyin": sentence_pinyin(natural, lexicon.get(db)),
        "traduction": _text(data.get("traduction"), 800),
        "erreurs": errors,
    }
