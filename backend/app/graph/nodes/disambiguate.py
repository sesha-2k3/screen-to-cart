from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graph.prompts import PROMPT_VERSION, tier2_messages
from app.graph.state import PipelineState
from app.llm.factory import Role
from app.llm.invoke import invoke_json
from app.schemas import Candidates


async def disambiguate(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Tier 2, text only: pick the exact model from Tier 1's candidates and notes."""
    tier1 = Candidates(candidates=state.get("candidates", []))
    messages = tier2_messages(
        tier1, state["title"], state["description"], state["transcript"]
    )
    result = await invoke_json(
        Role.DISAMBIGUATE, messages, Candidates, PROMPT_VERSION, config
    )
    return {"candidates": result.candidates, "tier": 2}
