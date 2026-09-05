"""Checkpointed session state and model ports for the shopping graph."""

from dataclasses import dataclass
from typing import TypedDict

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage
from langchain_core.runnables import Runnable
from langgraph.graph import MessagesState

from pricewise.regret.models import (
    CandidateBatch,
    RankingResult,
    RegretProfile,
    TurnPlan,
)
from pricewise.schemas import Receipt


class ShoppingState(MessagesState):
    """Planner initializes all fields before execution nodes can run."""

    profile: RegretProfile
    plan: TurnPlan
    ranking: RankingResult
    structured_response: Receipt | None
    tool_rounds: int
    asked_attributes: list[str]
    evidence_start: int


class StateUpdate(TypedDict, total=False):
    messages: list[AnyMessage]
    profile: RegretProfile
    plan: TurnPlan
    ranking: RankingResult
    structured_response: Receipt | None
    tool_rounds: int
    asked_attributes: list[str]
    evidence_start: int


@dataclass(frozen=True, slots=True)
class ModelPorts:
    planner: Runnable[LanguageModelInput, TurnPlan]
    researcher: Runnable[LanguageModelInput, BaseMessage]
    extractor: Runnable[LanguageModelInput, CandidateBatch]
    responder: Runnable[LanguageModelInput, BaseMessage]


def visible_history(state: ShoppingState) -> list[AnyMessage]:
    """Keep internal tool research out of the conversational planning context."""
    return [
        message
        for message in state["messages"]
        if isinstance(message, (HumanMessage, AIMessage))
        and not message.additional_kwargs.get("pricewise_internal")
    ]


def latest_user_text(state: ShoppingState) -> str:
    """Return the human words that may authorize this turn's patch."""
    return next(
        message.text
        for message in reversed(state["messages"])
        if isinstance(message, HumanMessage)
    )


def task_messages(state: ShoppingState) -> list[AnyMessage]:
    """Limit web evidence and references to the current shopping task."""
    return state["messages"][state.get("evidence_start", 0) :]
