from typing import Any

from langchain_core.runnables import RunnableConfig

from app.graph.confidence import rank
from app.graph.prompts import PROMPT_VERSION, tier1_messages
from app.graph.state import PipelineState
from app.llm.factory import Role
from app.llm.invoke import invoke_json
from app.schemas import Candidates


async def identify(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Tier 1: name the product from the sharpest frame and the video's text."""
    messages = tier1_messages(
        state["frame"], state["title"], state["description"], state["transcript"]
    )
    result = await invoke_json(
        Role.IDENTIFY_VISION, messages, Candidates, PROMPT_VERSION, config
    )
    return {"candidates": rank(result.candidates), "tier": 1}
