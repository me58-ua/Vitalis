from typing import Literal

from pydantic import BaseModel, Field


class ChatQuestion(BaseModel):
    id: str
    text: str
    block: str
    options: list[str] = Field(default_factory=list)


class ChatAnswer(BaseModel):
    question_id: str = Field(min_length=1, max_length=60)
    message: str = Field(min_length=1, max_length=4000)


class ChatConsent(BaseModel):
    accepted: bool


class ChatSkip(BaseModel):
    question_id: str = Field(min_length=1, max_length=60)


class ChatConfirmation(BaseModel):
    draft_id: str = Field(min_length=1, max_length=60)
    confirmed: bool


class ChatReview(BaseModel):
    question_id: str
    question: str
    answer: str
    summary: list[str]


class ChatPending(ChatReview):
    draft_id: str


class OnboardingChatState(BaseModel):
    stage: Literal["consent", "question", "confirmation", "completed", "declined"]
    question: ChatQuestion | None = None
    pending: ChatPending | None = None
    confirmed_answers: list[ChatReview] = Field(default_factory=list)
    completed_questions: int = 0
    total_questions: int = 13
    message: str | None = None
    skipped_questions: list[str] = Field(default_factory=list)
    auto_skipped_questions: list[str] = Field(default_factory=list)
    is_update: bool = False
