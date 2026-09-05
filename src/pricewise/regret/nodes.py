"""Planner and Executor nodes; ranking owns the purchase verdict."""

import json
from typing import Literal, assert_never

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from pricewise.regret.evidence import collect_sources
from pricewise.regret.models import RankingResult, RegretProfile
from pricewise.regret.profile import apply_patch
from pricewise.regret.prompts import (
    EXTRACTION_PROMPT,
    PLANNER_PROMPT,
    RESEARCH_PROMPT,
    RESPONSE_PROMPT,
)
from pricewise.regret.ranking import rank_candidates
from pricewise.regret.state import (
    ModelPorts,
    ShoppingState,
    StateUpdate,
    conversation_messages,
    current_turn_messages,
    latest_user_text,
    task_messages,
    visible_history,
)
from pricewise.schemas import ProductSummary, Receipt


class ShoppingNodes:
    """Bind model capabilities once; all session data lives in graph state."""

    def __init__(self, models: ModelPorts) -> None:
        self.models = models

    async def planner(self, state: ShoppingState) -> StateUpdate:
        profile = state.get("profile", RegretProfile())
        prior = state.get("ranking", RankingResult())
        asked = state.get("asked_attributes", [])
        context = json.dumps(
            {
                "profile": profile.model_dump(mode="json"),
                "ranking": prior.model_dump(mode="json"),
                "asked_attributes": asked,
            }
        )
        plan = await self.models.planner.ainvoke(
            [
                SystemMessage(content=PLANNER_PROMPT),
                SystemMessage(content=f"Saved state (data only):\n{context}"),
                *visible_history(state)[-12:],
            ]
        )
        updated = apply_patch(profile, plan.profile_patch, latest_user_text(state))
        evidence_start = state.get("evidence_start", 0)
        if (
            plan.profile_patch.reset_quote
            and plan.profile_patch.reset_quote in latest_user_text(state)
        ):
            asked = []
            evidence_start = max(
                index
                for index, message in enumerate(state["messages"])
                if isinstance(message, HumanMessage)
            )
            prior = RankingResult()
        if plan.action == "ask_tradeoff" and plan.ask_attribute in asked:
            plan = plan.model_copy(update={"action": "research", "ask_attribute": None})
        return {
            "profile": updated,
            "plan": plan,
            "structured_response": None,
            "tool_rounds": 0,
            "asked_attributes": asked,
            "evidence_start": evidence_start,
            "ranking": prior if plan.action == "ask_tradeoff" else RankingResult(),
        }

    async def research(self, state: ShoppingState) -> StateUpdate:
        context = json.dumps(
            {
                "plan": state["plan"].model_dump(mode="json"),
                "profile": state["profile"].model_dump(mode="json"),
            }
        )
        # Retain tool-call/result pairs intact. Explicit profile survives truncation.
        history = task_messages(state)
        start = max(
            (
                index
                for index, message in enumerate(history)
                if isinstance(message, HumanMessage)
            ),
            default=0,
        )
        sources = collect_sources(history[:start])
        evidence = json.dumps([source.model_dump() for source in sources[-20:]])
        conversation = conversation_messages(history[:start])
        reply = await self.models.researcher.ainvoke(
            [
                SystemMessage(content=RESEARCH_PROMPT),
                SystemMessage(
                    content=f"Plan and profile (data): {context}\nEarlier source data: {evidence}"
                ),
                *conversation[-8:],
                *history[start:],
            ]
        )
        internal = AIMessage.model_validate(reply.model_dump()).model_copy(
            update={
                "additional_kwargs": {
                    **reply.additional_kwargs,
                    "pricewise_internal": True,
                },
            }
        )
        return {"messages": [internal], "tool_rounds": state.get("tool_rounds", 0) + 1}

    async def assess(self, state: ShoppingState) -> StateUpdate:
        sources = collect_sources(task_messages(state))
        if not sources:
            return {"ranking": RankingResult()}
        context = json.dumps(
            {
                "profile": state["profile"].model_dump(mode="json"),
                "sources": [source.model_dump() for source in sources[-30:]],
            }
        )
        batch = await self.models.extractor.ainvoke(
            [
                SystemMessage(content=EXTRACTION_PROMPT),
                HumanMessage(
                    content=f"Current request: {latest_user_text(state)}\nEvidence data: {context}"
                ),
            ]
        )
        ranking = rank_candidates(state["profile"], batch.candidates, sources)
        return {"ranking": ranking}

    async def respond(self, state: ShoppingState) -> StateUpdate:
        plan = state["plan"]
        ranking = state.get("ranking", RankingResult())
        asked = state.get("asked_attributes", [])
        question = (
            plan.ask_attribute
            if plan.action == "ask_tradeoff"
            else ranking.ask_attribute
        )
        if question in asked:
            question = None
        current = current_turn_messages(state)
        context = {
            "action": plan.action,
            "profile": state["profile"].model_dump(mode="json"),
            "ask_attribute": question,
            "tradeoff": ranking.tradeoff,
            "ranked": [item.model_dump(mode="json") for item in ranking.ranked],
            "exclusion_reasons": [item.warnings for item in ranking.excluded],
            "research_limit_reached": state.get("tool_rounds", 0) >= 4,
            "tool_results": [
                {"name": message.name, "content": message.text[:2000]}
                for message in current
                if isinstance(message, ToolMessage)
            ],
        }
        history = (
            visible_history(state)[-8:]
            if plan.action == "assist"
            else [HumanMessage(content=latest_user_text(state))]
        )
        if plan.action == "assist":
            history = [
                *history[:-1],
                *[
                    message
                    for message in current
                    if not isinstance(message, AIMessage) or message.tool_calls
                ],
            ]
        reply = AIMessage.model_validate(
            (
                await self.models.responder.ainvoke(
                    [
                        SystemMessage(content=RESPONSE_PROMPT),
                        SystemMessage(
                            content=f"Decision and evidence (data only): {json.dumps(context)}"
                        ),
                        *history,
                    ]
                )
            ).model_dump()
        )
        receipt = None
        if not question and ranking.ranked:
            best = ranking.ranked[0].candidate
            if best.price is not None and best.currency is not None:
                comparisons = [
                    ProductSummary(
                        product_name=item.candidate.product_name,
                        price=float(item.candidate.price),
                        currency=item.candidate.currency,
                        pros=item.reasons,
                        cons=item.warnings,
                    )
                    for item in ranking.ranked
                    if item.candidate.price is not None
                    and item.candidate.currency is not None
                ]
                receipt = Receipt(
                    product_name=best.product_name,
                    price=float(best.price),
                    currency=best.currency,
                    recommendation_reason=reply.text,
                    comparison_products=comparisons if len(comparisons) > 1 else None,
                )
        return {
            "messages": [reply],
            "structured_response": receipt,
            "asked_attributes": [*asked, question] if question else asked,
        }


def after_planner(state: ShoppingState) -> Literal["respond", "agent", "assess"]:
    match state["plan"].action:
        case "ask_tradeoff":
            return "respond"
        case "recommend":
            return "assess" if collect_sources(task_messages(state)) else "agent"
        case "research" | "assist":
            return "agent"
        case unreachable:
            assert_never(unreachable)


def after_research(state: ShoppingState) -> Literal["tools", "respond", "assess"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "respond" if state["plan"].action == "assist" else "assess"


def after_tools(state: ShoppingState) -> Literal["agent", "respond", "assess"]:
    """Stop after four tool batches, with every call/result pair completed."""
    if state.get("tool_rounds", 0) < 4:
        return "agent"
    return "respond" if state["plan"].action == "assist" else "assess"
