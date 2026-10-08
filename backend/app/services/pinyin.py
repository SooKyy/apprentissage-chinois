import re
import unicodedata

from pypinyin import Style, lazy_pinyin, pinyin

_TONE_MARKS = {"a": "āáǎà", "e": "ēéěè", "i": "īíǐì", "o": "ōóǒò", "u": "ūúǔù", "ü": "ǖǘǚǜ"}
_COMBINING = ["̄", "́", "̌", "̀"]
_SYLLABLE = re.compile(r"^([A-Za-zÜü:]+)([1-5])$")
_CJK = re.compile(r"[㐀-䶿一-鿿]")
_HAN = r"[㐀-䶿一-鿿·]+"
_REF_BOTH = re.compile(rf"({_HAN})\|({_HAN})\[([^\]]+)\]")
_REF_ONE = re.compile(rf"({_HAN})\[([^\]]+)\]")
_REF_BARE = re.compile(rf"({_HAN})\|({_HAN})")
_REF_PINYIN = re.compile(r"\[((?:[A-Za-z:]+[1-5] ?)+)\]")


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text))


def syllable_to_accented(syllable: str) -> str:
    """'nu:3' -> 'nǚ', 'hao3' -> 'hǎo', 'de5' -> 'de'. Ce qui n'est pas une syllabe numérotée est rendu tel quel."""
    match = _SYLLABLE.match(syllable)
    if not match:
        return syllable
    body = match.group(1).replace("u:", "ü").replace("U:", "Ü")
    tone = int(match.group(2))
    if tone == 5:
        return body
    low = body.lower()
    if "a" in low:
        index = low.index("a")
    elif "e" in low:
        index = low.index("e")
    elif "ou" in low:
        index = low.index("o")
    else:
        vowels = [i for i, ch in enumerate(low) if ch in "iouü"]
        if not vowels:
            # syllabes sans voyelle de CC-CEDICT (m2, ng4, hng5…) : accent combinant sur la 1re lettre
            return unicodedata.normalize("NFC", body[0] + _COMBINING[tone - 1] + body[1:])
        index = vowels[-1]
    marked = _TONE_MARKS[low[index]][tone - 1]
    if body[index].isupper():
        marked = marked.upper()
    return body[:index] + marked + body[index + 1 :]


def numeric_to_accented(numeric: str) -> str:
    """'nu:3 peng2 you5' -> 'nǚ péng you'."""
    return " ".join(syllable_to_accented(part) for part in numeric.split())


def plain(text: str) -> str:
    """Clé de recherche pinyin : sans tons, espaces ni chiffres, ü -> v. Accepte numérique ou accentué."""
    text = text.lower().replace("u:", "v").replace("ü", "v")
    for base, marks in _TONE_MARKS.items():
        for mark in marks:
            text = text.replace(mark, "v" if base == "ü" else base)
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if ch.isascii() and ch.isalpha())


def clean_definition(definition: str) -> str:
    """Rend lisibles les renvois CC-CEDICT : '個|个[ge4]' -> '个 (gè)'."""
    definition = _REF_BOTH.sub(lambda m: f"{m.group(2)} ({numeric_to_accented(m.group(3))})", definition)
    definition = _REF_ONE.sub(lambda m: f"{m.group(1)} ({numeric_to_accented(m.group(2))})", definition)
    definition = _REF_BARE.sub(lambda m: m.group(2), definition)
    definition = _REF_PINYIN.sub(lambda m: f"[{numeric_to_accented(m.group(1))}]", definition)
    return definition.strip()


def primary_numeric(word: str) -> str:
    """Lecture la plus probable d'un mot selon pypinyin, au format numérique CC-CEDICT."""
    parts = lazy_pinyin(word, style=Style.TONE3, neutral_tone_with_five=True, v_to_u=False)
    return " ".join(parts).replace("v", "u:")


_OPENING = "“‘(（《【"
_RUNS = re.compile(r"([\u3400-\u4dbf\u4e00-\u9fff]+)")
_MAX_WORD = 6
_UNKNOWN_COST = 16.0

# mot -> (syllabes de la lecture principale, ou None pour un caractère seul ; coût = -log de sa fréquence)
Lexicon = dict[str, tuple[list[str] | None, float]]

# Caractères isolés dont la lecture dépend du voisinage et que pypinyin lit mal
_SUBJECTS = {"我", "你", "他", "她", "它", "您", "我们", "你们", "他们", "她们", "咱们", "还", "也", "就", "都", "又", "可", "总"}
_DEGREES = {"很", "太", "真", "好", "更", "最", "挺", "不", "多", "非常", "比较", "这么", "那么", "有点", "有点儿", "特别"}


def segment(run: str, lexicon: Lexicon) -> list[str]:
    """Découpe une suite de caractères en mots du dictionnaire : découpage le plus probable (unigramme)."""
    size = len(run)
    best = [0.0] + [float("inf")] * size
    back = [0] * (size + 1)
    for end in range(1, size + 1):
        for length in range(1, min(_MAX_WORD, end) + 1):
            entry = lexicon.get(run[end - length : end])
            if entry is None and length > 1:
                continue
            cost = best[end - length] + (entry[1] if entry else _UNKNOWN_COST)
            if cost < best[end]:
                best[end], back[end] = cost, length
    words: list[str] = []
    end = size
    while end > 0:
        words.append(run[end - back[end] : end])
        end -= back[end]
    return words[::-1]


def _standalone(char: str, default: str, previous: str | None, following: str) -> str:
    if char == "得":
        if following[:1] in ("了", "到", "过"):
            return "dé"
        return "děi" if previous is None or previous in _SUBJECTS else "de"
    if char == "地":
        return "de" if previous is not None and len(previous) >= 2 else default
    if char == "教":
        return "jiāo"
    if char == "长" and previous in _DEGREES:
        return "cháng"
    return default


def _run_syllables(run: str, lexicon: Lexicon) -> list[str]:
    """Une syllabe par caractère. pypinyin donne la lecture en contexte, puis les mots du dictionnaire
    imposent la leur : pypinyin ignore le ton neutre lexical (喜欢 « xǐ huān » au lieu de « xǐ huan »)."""
    syllables = lazy_pinyin(run, style=Style.TONE)
    if len(syllables) != len(run):
        return syllables
    index = 0
    previous: str | None = None
    for word in segment(run, lexicon):
        entry = lexicon.get(word)
        if len(word) > 1 and entry and entry[0]:
            syllables[index : index + len(word)] = entry[0]
        elif len(word) == 1:
            syllables[index] = _standalone(word, syllables[index], previous, run[index + 1 :])
        index += len(word)
        previous = word
    return syllables


def sentence_pinyin(text: str, lexicon: Lexicon | None = None) -> str:
    """Pinyin accentué d'une phrase, syllabes séparées par des espaces, ponctuation conservée."""
    out = ""
    glue = False  # vrai juste après une ponctuation ouvrante : pas d'espace avant la syllabe suivante
    for position, run in enumerate(_RUNS.split(text)):
        pieces = _run_syllables(run, lexicon or {}) if position % 2 else run.split()
        for piece in pieces:
            opening = piece[0] in _OPENING
            if out and not glue and (piece[0].isalnum() or opening):
                out += " "
            out += piece
            glue = piece[-1] in _OPENING
    return out
