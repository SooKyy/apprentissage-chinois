from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# Toutes les dates sont stockées en UTC naïf (voir app.services.clock).


class Word(Base):
    __tablename__ = "words"
    # Index couvrant : compter les mots à trier ou une tranche de fréquence sans lire la table
    __table_args__ = (Index("ix_words_triage", "freq_rank", "is_proper", "hsk"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simp: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    trad: Mapped[str] = mapped_column(String(64))
    pinyin: Mapped[str] = mapped_column(String(255))
    # [{"pinyin", "num", "trad", "en": [...], "fr": [...]}], lecture principale en premier
    readings: Mapped[list] = mapped_column(JSON)
    gloss_en: Mapped[str] = mapped_column(Text, default="")
    gloss_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    hsk: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    freq_rank: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    is_proper: Mapped[bool] = mapped_column(Boolean, default=False)
    # Enrichissement LLM (sens français court + note d'usage)
    llm_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["UserWord | None"] = relationship(back_populates="word", uselist=False)
    sentences: Mapped[list["Sentence"]] = relationship(back_populates="word", order_by="Sentence.id")


class WordPinyin(Base):
    __tablename__ = "word_pinyin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), index=True)
    # pinyin sans tons ni espaces, ü -> v (ex. "nvpengyou")
    plain: Mapped[str] = mapped_column(String(255), index=True)


class UserWord(Base):
    __tablename__ = "user_words"

    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), index=True)  # learning | known | ignored
    source: Mapped[str] = mapped_column(String(16), default="dico")  # dico | tri | placement | llm
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

    word: Mapped[Word] = relationship(back_populates="user")


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (UniqueConstraint("word_id", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # reco | ecoute | prod
    # État FSRS sérialisé (Card.to_dict) ; NULL tant que la carte n'a jamais été vue
    fsrs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    state: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 learning, 2 review, 3 relearning
    due: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    introduced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_review: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    word: Mapped[Word] = relationship()


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1 again, 2 hard, 3 good, 4 easy
    state_before: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = carte neuve
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # État de la carte avant la réponse, pour pouvoir annuler
    snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Sentence(Base):
    __tablename__ = "sentences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), index=True)
    zh: Mapped[str] = mapped_column(Text)
    pinyin: Mapped[str] = mapped_column(Text)
    fr: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="llm")
    created_at: Mapped[datetime] = mapped_column(DateTime)

    word: Mapped[Word] = relationship(back_populates="sentences")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[object] = mapped_column(JSON)
