"""Importe CC-CEDICT, CFDICT, les niveaux HSK 3.0 et les rangs de fréquence dans la table words.

Usage (depuis backend/) :
    .venv/bin/python -I scripts/import_dictionaries.py CEDICT.txt.gz CFDICT.u8 HSK.json

Réimportable sans risque : les mots existants sont mis à jour sur place (les id ne changent
jamais, ils sont référencés par les cartes), aucun mot n'est supprimé.
"""

import gzip
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wordfreq import top_n_list  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Word, WordPinyin  # noqa: E402
from app.services import pinyin as py  # noqa: E402

LINE = re.compile(r"^(\S+) (\S+) \[([^\]]*)\] /(.*)/\s*$")
SECONDARY = re.compile(r"^(CL:|variant of|old variant of|see |see also |also written|surname |abbr\. for|erhua variant)", re.I)
MAX_FREQ_WORDS = 200_000


def parse(lines):
    """Rend (trad, simp, pinyin_numérique, [définitions]) pour chaque entrée au format CEDICT."""
    for line in lines:
        if line.startswith("#"):
            continue
        match = LINE.match(line.rstrip("\r\n"))
        if not match:
            continue
        trad, simp, numeric, body = match.groups()
        defs = [py.clean_definition(d) for d in body.split("/") if d.strip()]
        if defs:
            yield trad, simp, numeric.strip(), defs


def is_proper_reading(numeric: str) -> bool:
    return numeric[:1].isupper()


def neutral_variant(a: str, b: str) -> bool:
    """Vrai si deux lectures numériques ne diffèrent que par un ton neutre ('xia4 mian5' / 'xia4 mian4')."""
    left, right = a.lower().split(), b.lower().split()
    return len(left) == len(right) and all(
        x == y or (x[:-1] == y[:-1] and "5" in (x[-1:], y[-1:])) for x, y in zip(left, right)
    )


def build(cedict_path: Path, cfdict_path: Path) -> dict[str, dict]:
    french: dict[tuple[str, str], list[str]] = {}
    french_by_form: dict[tuple[str, str], dict[str, list[str]]] = {}
    french_by_simp: dict[str, list[list[str]]] = {}
    with open(cfdict_path, encoding="utf-8") as handle:
        for trad, simp, numeric, defs in parse(handle):
            french.setdefault((simp, numeric.lower()), []).extend(defs)
            french_by_form.setdefault((trad, simp), {}).setdefault(numeric.lower(), []).extend(defs)
            french_by_simp.setdefault(simp, []).append(defs)

    words: dict[str, dict] = {}
    with gzip.open(cedict_path, "rt", encoding="utf-8") as handle:
        for trad, simp, numeric, defs in parse(handle):
            if not py.has_cjk(simp):
                continue
            entry = words.setdefault(simp, {"readings": {}})
            reading = entry["readings"].setdefault(numeric, {"num": numeric, "trad": trad, "en": [], "_trads": []})
            reading["en"].extend(d for d in defs if d not in reading["en"])
            if trad not in reading["_trads"]:
                reading["_trads"].append(trad)

    for simp, entry in words.items():
        primary = py.primary_numeric(simp).lower()
        readings = list(entry["readings"].values())
        known = {reading["num"].lower() for reading in readings}
        for index, reading in enumerate(readings):
            reading["pinyin"] = py.numeric_to_accented(reading["num"])
            num = reading["num"].lower()
            # Homographes en simplifié (下面 « dessous » / 下麵 « cuire des nouilles ») : on suit l'ordre
            # des formes traditionnelles de CC-CEDICT, pas celui de CFDICT.
            fr: list[str] = []
            for trad in reading.pop("_trads"):
                by_num = french_by_form.get((trad, simp), {})
                defs = by_num.get(num)
                if defs is None:
                    # CFDICT note souvent au ton neutre ce que CC-CEDICT donne au ton plein
                    defs = next((d for n, d in by_num.items() if n not in known and neutral_variant(n, num)), [])
                fr.extend(d for d in defs if d not in fr)
            reading["fr"] = fr or french.get((simp, num), [])
            # Mot de plusieurs caractères à lectures multiples : la variante au ton neutre est le sens
            # courant à l'oral (东西 dōng xi « chose » avant dōng xī « est et ouest »).
            neutral = len(simp) > 1 and reading["num"].endswith("5")
            reading["_order"] = (is_proper_reading(reading["num"]), not neutral, reading["num"].lower() != primary, index)
        # CFDICT ne distingue pas toujours la lecture : si le mot n'en a qu'une, on rattache quand même
        if len(readings) == 1 and not readings[0]["fr"] and len(french_by_simp.get(simp, [])) == 1:
            readings[0]["fr"] = french_by_simp[simp][0]
        readings.sort(key=lambda r: r.pop("_order"))
        entry["readings"] = readings
        entry["is_proper"] = all(is_proper_reading(r["num"]) for r in readings)
        first = readings[0]
        main_en = [d for d in first["en"] if not SECONDARY.match(d)] or first["en"]
        entry["gloss_en"] = "; ".join(main_en[:4])
        fr = first["fr"] or next((r["fr"] for r in readings if r["fr"]), [])
        entry["gloss_fr"] = "; ".join(fr[:4]) or None
        entry["trad"] = first["trad"]
        entry["pinyin"] = first["pinyin"]
    return words


def hsk_levels(hsk_path: Path) -> dict[str, int]:
    levels: dict[str, int] = {}
    for item in json.loads(hsk_path.read_text(encoding="utf-8")):
        new = [int(tag.split("-")[1]) for tag in item.get("level", []) if tag.startswith("new-")]
        if new:
            levels[item["simplified"]] = min(new)
    return levels


def frequency_ranks(known: set[str]) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for token in top_n_list("zh", MAX_FREQ_WORDS, wordlist="large"):
        if token in known and token not in ranks:
            ranks[token] = len(ranks) + 1
    return ranks


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    cedict_path, cfdict_path, hsk_path = (Path(arg) for arg in sys.argv[1:])
    words = build(cedict_path, cfdict_path)
    levels = hsk_levels(hsk_path)
    ranks = frequency_ranks(set(words))

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing = {word.simp: word for word in db.query(Word).all()}
        created = 0
        for simp, entry in words.items():
            word = existing.get(simp)
            if word is None:
                word = Word(simp=simp)
                db.add(word)
                created += 1
            word.trad = entry["trad"]
            word.pinyin = entry["pinyin"]
            word.readings = entry["readings"]
            word.gloss_en = entry["gloss_en"]
            word.gloss_fr = entry["gloss_fr"]
            word.is_proper = entry["is_proper"]
            word.hsk = levels.get(simp)
            word.freq_rank = ranks.get(simp)
        db.flush()
        db.query(WordPinyin).delete()
        ids = {word.simp: word.id for word in db.query(Word).all()}
        rows = []
        for simp, entry in words.items():
            for key in {py.plain(reading["num"]) for reading in entry["readings"]}:
                if key:
                    rows.append({"word_id": ids[simp], "plain": key})
        db.bulk_insert_mappings(WordPinyin, rows)
        db.commit()
        with_fr = sum(1 for entry in words.values() if entry["gloss_fr"])
        print(f"mots: {len(words)} (nouveaux: {created}) | avec français: {with_fr} | "
              f"HSK: {sum(1 for s in words if s in levels)} | classés par fréquence: {len(ranks)}")


if __name__ == "__main__":
    main()
