"""A flat LangGraph preserves existing tool interrupts and SSE event names."""

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from pricewise.regret.models import CandidateBatch, TurnPlan
from pricewise.regret.recovery import recover_output, require_response
from pricewise.regret.nodes import (
    ShoppingNodes,
    after_planner,
    after_research,
    after_tools,
)
from pricewise.regret.state import ModelPorts, ShoppingState, StateUpdate


def compile_graph(
    models: ModelPorts,
    tools: list[BaseTool],
    checkpointer: BaseCheckpointSaver[str],
) -> CompiledStateGraph[ShoppingState, None, StateUpdate, ShoppingState]:
    """Compile independent planning, research, assessment, and response nodes."""
    nodes = ShoppingNodes(models)
    builder = StateGraph(ShoppingState, input_schema=StateUpdate)
    builder.add_node("planner", nodes.planner)
    builder.add_node("agent", nodes.research)
    builder.add_node("tools", ToolNode(tools))
    builder.add_node("assess", nodes.assess)
    builder.add_node("respond", nodes.respond)
    builder.add_edge(START, "planner")
    builder.add_conditional_edges("planner", after_planner)
    builder.add_conditional_edges("agent", after_research)
    builder.add_conditional_edges("tools", after_tools)
    builder.add_edge("assess", "respond")
    builder.add_edge("respond", END)
    return builder.compile(checkpointer=checkpointer)


def create_regret_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    checkpointer: BaseCheckpointSaver[str],
) -> CompiledStateGraph[ShoppingState, None, StateUpdate, ShoppingState]:
    """Use typed model outputs for decisions and extraction, text only at the end."""
    models = ModelPorts(
        planner=recover_output(
            model.with_structured_output(TurnPlan, method="function_calling")
            | RunnableLambda(TurnPlan.model_validate)
        ),
        researcher=model.bind_tools(tools),
        extractor=recover_output(
            model.with_structured_output(CandidateBatch, method="function_calling")
            | RunnableLambda(CandidateBatch.model_validate)
        ),
        responder=recover_output(model | RunnableLambda(require_response)),
    )
    return compile_graph(models, tools, checkpointer)
