from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.config import get_settings
from app.graph.nodes.disambiguate import disambiguate
from app.graph.nodes.identify import identify
from app.graph.state import PipelineState
from app.schemas import ProductCandidate


def needs_tier2(candidates: list[ProductCandidate], threshold: float) -> bool:
    if not candidates:
        return False
    return len(candidates) > 1 or candidates[0].confidence < threshold


def _after_identify(state: PipelineState) -> Literal["disambiguate", "done"]:
    threshold = get_settings().tier2_confidence_threshold
    if needs_tier2(state.get("candidates", []), threshold):
        return "disambiguate"
    return "done"


def build_graph() -> CompiledStateGraph[PipelineState]:
    graph = StateGraph(PipelineState)
    graph.add_node("identify", identify)
    graph.add_node("disambiguate", disambiguate)
    graph.add_edge(START, "identify")
    graph.add_conditional_edges(
        "identify", _after_identify, {"disambiguate": "disambiguate", "done": END}
    )
    graph.add_edge("disambiguate", END)
    return graph.compile()
