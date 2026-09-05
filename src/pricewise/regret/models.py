"""Validated contracts at the planner and web-evidence boundaries."""

from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Priority = Literal["forbidden", "negotiable", "important"]
Outcome = Literal["matched", "contradicted", "unknown"]
Action = Literal["ask_tradeoff", "research", "recommend", "assist"]


class Contract(BaseModel):
    """Immutable model output parsed at the graph boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class Criterion(Contract):
    key: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=400)
    level: Priority
    source_quote: str = Field(min_length=1)


class BudgetLimit(Contract):
    amount: Decimal = Field(gt=0, allow_inf_nan=False)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    level: Literal["forbidden", "negotiable"] = "forbidden"
    source_quote: str = Field(min_length=1)


class Removal(Contract):
    key: str
    source_quote: str = Field(min_length=1)


class ProfilePatch(Contract):
    upsert: list[Criterion] = Field(default_factory=list, max_length=20)
    remove: list[Removal] = Field(default_factory=list, max_length=20)
    budget: BudgetLimit | None = None
    clear_budget_quote: str | None = None
    reset_quote: str | None = None


class RegretProfile(Contract):
    criteria: list[Criterion] = Field(default_factory=list)
    budget: BudgetLimit | None = None


class TurnPlan(Contract):
    action: Action
    profile_patch: ProfilePatch = Field(default_factory=ProfilePatch)
    ask_attribute: str | None = None

    @model_validator(mode="after")
    def require_question_target(self) -> Self:
        if self.action == "ask_tradeoff" and not self.ask_attribute:
            message = "ask_tradeoff requires one ask_attribute"
            raise ValueError(message)
        return self


class Source(Contract):
    url: str = Field(pattern=r"^https?://\S+$")
    text: str


class Assessment(Contract):
    key: str
    outcome: Outcome
    quote: str = ""


class Candidate(Contract):
    product_name: str = Field(min_length=1)
    source_url: str = Field(pattern=r"^https?://\S+$")
    price: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    price_quote: str = ""
    assessments: list[Assessment] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_assessments(self) -> Self:
        keys = [assessment.key for assessment in self.assessments]
        if len(keys) != len(set(keys)):
            message = "Each criterion may have only one assessment per candidate"
            raise ValueError(message)
        return self


class CandidateBatch(Contract):
    candidates: list[Candidate] = Field(default_factory=list, max_length=15)


class RankedCandidate(Contract):
    candidate: Candidate
    score: float
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RankingResult(Contract):
    ranked: list[RankedCandidate] = Field(default_factory=list)
    excluded: list[RankedCandidate] = Field(default_factory=list)
    ask_attribute: str | None = None
    tradeoff: list[str] = Field(default_factory=list)
