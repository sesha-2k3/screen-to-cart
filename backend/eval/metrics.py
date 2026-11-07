"""Exact-match scoring: brand and model must match after normalizing."""

import re
import unicodedata

from app.schemas import ProductCandidate


def normalize(text: str) -> str:
    # NFKD splits "é" into "e" + an accent mark, so "Aimé" and "Aime" match.
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


# Label brand for generic products where any brand is right (e.g. "tongue scraper").
ANY_BRAND = "any"


def is_match(brand: str, model: str, candidate: ProductCandidate) -> bool:
    """True when the labeled brand and model both appear in the candidate.

    Containment rather than equality, so "Sony" + "WH-1000XM5" matches a candidate
    whose model is "Sony WH-1000XM5 Wireless".
    """
    label_brand, label_model = normalize(brand), normalize(model)
    if not label_brand or not label_model:
        return False
    full_name = normalize(candidate.brand + candidate.model)
    if label_brand == ANY_BRAND:
        return label_model in full_name
    return label_brand in normalize(candidate.brand) and label_model in full_name


def top1_correct(brand: str, model: str, candidates: list[ProductCandidate]) -> bool:
    return bool(candidates) and is_match(brand, model, candidates[0])
