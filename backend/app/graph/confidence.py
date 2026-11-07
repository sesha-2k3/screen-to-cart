from app.schemas import ProductCandidate


def rank(candidates: list[ProductCandidate]) -> list[ProductCandidate]:
    """Sort best first and scale confidences down so they add up to at most 1.

    The prompt asks for this, but models often give every candidate 0.9+. Scaling
    keeps the Tier 2 margin rule meaningful when they do.
    """
    ranked = sorted(candidates, key=lambda c: c.confidence, reverse=True)
    total = sum(c.confidence for c in ranked)
    if total <= 1:
        return ranked
    return [c.model_copy(update={"confidence": c.confidence / total}) for c in ranked]
