import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="chinois-tests-")
os.environ.update(
    DATABASE_URL=f"sqlite:///{_tmp}/test.db",
    SECRET_KEY="test-secret",
    ADMIN_PASSWORD="test-password",
    OPENROUTER_API_KEY="",
    TTS_CACHE_DIR=f"{_tmp}/tts",
    APP_TIMEZONE="Europe/Paris",
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Word, WordPinyin  # noqa: E402
from app.services import lexicon  # noqa: E402
from app.services import pinyin as py  # noqa: E402

WORDS = [
    # simp, trad, numérique, anglais, français, hsk, rang, nom propre
    ("的", "的", "de5", "of; ~'s (possessive particle)", "de (particule possessive)", 1, 1, False),
    ("吃", "吃", "chi1", "to eat", "manger", 1, 2, False),
    ("东西", "東西", "dong1 xi5", "thing; stuff", "chose; truc", 1, 3, False),
    ("中国", "中國", "Zhong1 guo2", "China", "Chine", 1, 4, True),
    ("女朋友", "女朋友", "nu:3 peng2 you5", "girlfriend", "petite amie", 1, 5, False),
    ("喜欢", "喜歡", "xi3 huan5", "to like; to be fond of", "aimer; apprécier", 1, 6, False),
    ("吃饭", "吃飯", "chi1 fan4", "to have a meal; to eat", "prendre un repas", 1, 7, False),
    ("绿", "綠", "lu:4", "green", "vert", 2, 8, False),
    ("难吃", "難吃", "nan2 chi1", "unpalatable", None, None, None, False),
]


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    for simp, trad, numeric, en, fr, hsk, rank, proper in WORDS:
        accented = py.numeric_to_accented(numeric)
        word = Word(
            simp=simp, trad=trad, pinyin=accented, gloss_en=en, gloss_fr=fr, hsk=hsk, freq_rank=rank,
            is_proper=proper,
            readings=[{"pinyin": accented, "num": numeric, "trad": trad, "en": en.split("; "), "fr": (fr or "").split("; ")}],
        )
        session.add(word)
        session.flush()
        session.add(WordPinyin(word_id=word.id, plain=py.plain(numeric)))
    session.commit()
    lexicon.reset()
    yield session
    session.close()


@pytest.fixture()
def client(db):
    client = TestClient(app)
    token = client.post("/api/auth/login", json={"password": "test-password"}).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture()
def word(db):
    return lambda simp: db.query(Word).filter(Word.simp == simp).one()


# 7 oct. 2026 à 10:00 heure de Paris (UTC+2)
NOW = datetime(2026, 10, 7, 8, 0, 0)
