from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.config import get_settings
from app.graph.nodes.disambiguate import disambiguate
from app.graph.nodes.identify import identify
from app.graph.state import PipelineState
from app.schemas import ProductCandidate


def needs_tier2(
    candidates: list[ProductCandidate], threshold: float, margin: float
) -> bool:
    """Unsure, a close runner-up, or a top guess the frame doesn't support."""
    if not candidates:
        return False
    top = candidates[0]
    if top.confidence < threshold:
        return True
    if len(candidates) > 1 and top.confidence - candidates[1].confidence < margin:
        return True
    # A name taken only from the text is the most common v1 mistake.
    return not any(item.source == "visual" for item in top.evidence)


def _after_identify(state: PipelineState) -> Literal["disambiguate", "done"]:
    settings = get_settings()
    candidates = state.get("candidates", [])
    if needs_tier2(
        candidates, settings.tier2_confidence_threshold, settings.tier2_margin
    ):
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
