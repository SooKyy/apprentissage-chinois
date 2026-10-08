from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StatusRequest(BaseModel):
    status: Literal["learning", "known", "ignored"]
    source: Literal["dico", "tri", "placement", "llm"] = "dico"


class AnswerRequest(BaseModel):
    rating: Literal[1, 2, 3, 4]
    duration_ms: int | None = Field(default=None, ge=0, le=3_600_000)


class PlacementAnswer(BaseModel):
    word_id: int
    known: bool


class PlacementRequest(BaseModel):
    answers: list[PlacementAnswer] = Field(min_length=1, max_length=500)


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)


class CorrectRequest(BaseModel):
    text: str = Field(min_length=1, max_length=600)
    intention: str = Field(default="", max_length=300)
