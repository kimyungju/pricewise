"""Script only model decisions; execute the real graph, tools, and HTTP routes."""

from dataclasses import dataclass

from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from pricewise.middleware.selective_interrupt import with_approval
from pricewise.regret.graph import compile_graph
from pricewise.regret.models import (
    Assessment,
    BudgetLimit,
    Candidate,
    CandidateBatch,
    Criterion,
    ProfilePatch,
    TurnPlan,
)
from pricewise.regret.state import ModelPorts

FIRST_MESSAGE = "편하고 날렵한 구두, USD 100 이하"
SECOND_MESSAGE = "디자인은 투박해도 좋아. 편안함이 중요해."


@dataclass(frozen=True, slots=True)
class Scenario:
    graph: CompiledStateGraph
    planner_calls: list[LanguageModelInput]
    tool_calls: list[str]


def shopping_scenario() -> Scenario:
    planner_calls: list[LanguageModelInput] = []
    tool_calls: list[str] = []
    plans = iter(
        [
            TurnPlan(
                action="research",
                profile_patch=ProfilePatch(
                    upsert=[
                        Criterion(
                            key="comfort",
                            description="Long wear comfort",
                            level="important",
                            source_quote="편하고",
                        ),
                        Criterion(
                            key="design",
                            description="Sleek design",
                            level="important",
                            source_quote="날렵한",
                        ),
                    ],
                    budget=BudgetLimit(
                        amount=100, currency="USD", source_quote="USD 100 이하"
                    ),
                ),
            ),
            TurnPlan(
                action="recommend",
                profile_patch=ProfilePatch(
                    upsert=[
                        Criterion(
                            key="design",
                            description="Sleek design",
                            level="negotiable",
                            source_quote="디자인은 투박해도 좋아",
                        ),
                    ]
                ),
            ),
        ]
    )

    def planner(inputs: LanguageModelInput) -> TurnPlan:
        planner_calls.append(inputs)
        return next(plans)

    research_replies = iter(
        [
            AIMessage(
                content="internal-research-only",
                tool_calls=[
                    {
                        "name": "search_product",
                        "args": {"query": "wedding shoes"},
                        "id": "search-1",
                    }
                ],
            ),
            AIMessage(content="internal-research-complete"),
        ]
    )

    @tool
    def search_product(query: str) -> str:
        """Return two recorded web listings for an offline workflow test."""
        tool_calls.append(query)
        return (
            "1. Comfort Shoe USD 90. Comfortable. Chunky.\n   URL: https://shop.example/a\n\n"
            "2. Sleek Shoe USD 95. Painful. Sleek.\n   URL: https://shop.example/b"
        )

    batch = CandidateBatch(
        candidates=[
            Candidate(
                product_name="Comfort Shoe",
                source_url="https://shop.example/a",
                price=90,
                price_quote="USD 90",
                assessments=[
                    Assessment(key="comfort", outcome="matched", quote="Comfortable"),
                    Assessment(key="design", outcome="contradicted", quote="Chunky"),
                ],
            ),
            Candidate(
                product_name="Sleek Shoe",
                source_url="https://shop.example/b",
                price=95,
                price_quote="USD 95",
                assessments=[
                    Assessment(key="comfort", outcome="contradicted", quote="Painful"),
                    Assessment(key="design", outcome="matched", quote="Sleek"),
                ],
            ),
        ]
    )
    models = ModelPorts(
        planner=RunnableLambda(planner),
        researcher=RunnableLambda(lambda _messages: next(research_replies)),
        extractor=RunnableLambda(lambda _messages: batch),
        responder=FakeListChatModel(
            responses=[
                "오래 신었을 때의 편안함과 날렵한 디자인 중 어느 쪽이 더 중요하세요?",
                "Comfort Shoe를 추천해요. 편안함을 우선하고 투박한 디자인을 받아들이는 선택이에요.",
            ]
        ),
    )
    return Scenario(
        compile_graph(models, [with_approval(search_product)], InMemorySaver()),
        planner_calls,
        tool_calls,
    )
