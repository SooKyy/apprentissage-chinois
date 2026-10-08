import pytest

from app.services import pinyin as py


@pytest.mark.parametrize(
    ("numeric", "accented"),
    [
        ("hao3", "hǎo"),
        ("nu:3 peng2 you5", "nǚ péng you"),
        ("lu:e4", "lüè"),
        ("Zhong1 guo2", "Zhōng guó"),
        ("dui4", "duì"),
        ("liu2", "liú"),
        ("gou3", "gǒu"),
        ("xiong2", "xióng"),
        ("er2", "ér"),
        ("r5", "r"),
        ("A xing2", "A xíng"),
        ("E2", "É"),
    ],
)
def test_numeric_to_accented(numeric, accented):
    assert py.numeric_to_accented(numeric) == accented


def test_plain_is_the_same_key_for_every_spelling():
    assert py.plain("nu:3 peng2 you5") == py.plain("nǚ péng you") == py.plain("Nv Peng You") == "nvpengyou"
    assert py.plain("lüè") == "lve"


def test_clean_definition_rewrites_cedict_references():
    assert py.clean_definition("CL:家[jia1],個|个[ge4]") == "CL:家 (jiā),个 (gè)"
    assert py.clean_definition("variant of 瞭|了[liao3]") == "variant of 了 (liǎo)"
    assert py.clean_definition("also pr. [shui2]") == "also pr. [shuí]"


def test_sentence_pinyin_keeps_punctuation_attached():
    assert py.sentence_pinyin("你好，我很好！") == "nǐ hǎo， wǒ hěn hǎo！"
    assert py.sentence_pinyin("他说：“好的。”") == "tā shuō：“hǎo de。”"


def test_has_cjk():
    assert py.has_cjk("abc 你") and not py.has_cjk("abc 123")


def lex(**words):
    """Mini-lexique : mot="lecture rang" (lecture omise pour un caractère seul)."""
    import math

    out = {}
    for word, spec in words.items():
        *reading, rank = spec.split()
        out[word] = (reading or None, math.log(int(rank)) + 2.5)
    return out


LEXICON = lex(
    喜欢="xǐ huan 200", 东西="dōng xi 260", 女朋友="nǚ péng you 3400", 朋友="péng you 300", 中文="Zhōng wén 1500",
    说中="shuō zhòng 60000", 慢慢="màn màn 2500", 我="1", 说="20", 中="15", 文="800", 会="25", 你="10", 得="150",
)


def test_sentence_pinyin_prefers_dictionary_readings_for_known_words():
    assert py.sentence_pinyin("我喜欢吃", LEXICON) == "wǒ xǐ huan chī"
    assert py.sentence_pinyin("我女朋友买了东西。", LEXICON) == "wǒ nǚ péng you mǎi le dōng xi。"
    assert py.sentence_pinyin("OK，喜欢 abc", LEXICON) == "OK， xǐ huan abc"
    assert py.sentence_pinyin("", LEXICON) == ""


def test_segmentation_prefers_frequent_words_over_longest_match():
    # 说中 (« tomber juste ») existe au dictionnaire mais ne doit pas avaler le 中 de 中文
    assert py.segment("你会说中文", LEXICON) == ["你", "会", "说", "中文"]
    assert py.sentence_pinyin("你会说中文吗", LEXICON) == "nǐ huì shuō Zhōng wén ma"
    assert py.segment("女朋友", LEXICON) == ["女朋友"]
    assert py.segment("囧囧", {}) == ["囧", "囧"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("你说得对", "nǐ shuō de duì"),
        ("我得走了", "wǒ děi zǒu le"),
        ("他得了第一", "tā dé le dì yī"),
        ("慢慢地走", "màn màn de zǒu"),
        ("教我", "jiāo wǒ"),
        ("头发很长", "tóu fà hěn cháng"),
    ],
)
def test_standalone_characters_read_from_their_neighbours(text, expected):
    assert py.sentence_pinyin(text, LEXICON) == expected
