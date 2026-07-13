from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from comptis.application.rapprochement.ports import McpClient, ReconciliationMemory
from comptis.infrastructure.agents.rapprochement.llm_arbiter import LLMArbiter
from comptis.infrastructure.agents.rapprochement.nodes.fetch import make_fetch_node
from comptis.infrastructure.agents.rapprochement.nodes.human_review import human_review
from comptis.infrastructure.agents.rapprochement.nodes.match import make_match_node
from comptis.infrastructure.agents.rapprochement.nodes.report import report
from comptis.infrastructure.agents.rapprochement.state import ReconciliationState


def build_reconciliation_graph(
    mcp_client: McpClient,
    memory: ReconciliationMemory,
    arbiter: LLMArbiter | None = None,
):
    if arbiter is None:
        arbiter = LLMArbiter()

    fetch = make_fetch_node(mcp_client, memory)
    match = make_match_node(mcp_client, memory, arbiter)

    builder = StateGraph(ReconciliationState)
    builder.add_node("fetch", fetch)
    builder.add_node("match", match)
    builder.add_node("human_review", human_review)
    builder.add_node("report", report)

    builder.add_edge(START, "fetch")
    builder.add_edge("fetch", "match")

    def route_after_match(state: ReconciliationState) -> str:
        if state.get("pending_review"):
            return "human_review"
        return "report"

    builder.add_conditional_edges("match", route_after_match, ["human_review", "report"])
    builder.add_edge("human_review", "report")
    builder.add_edge("report", END)

    return builder.compile(interrupt_before=["human_review"])
