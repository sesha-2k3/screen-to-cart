from app.schemas import ProductCandidate
from eval.metrics import is_match, top1_correct


def candidate(brand: str, model: str) -> ProductCandidate:
    return ProductCandidate(
        brand=brand,
        model=model,
        category="headphones",
        confidence=0.9,
        evidence=[],
        search_queries=[],
        visual_notes="",
    )


def test_is_match_ignores_case_punctuation_and_extra_words() -> None:
    assert is_match("Sony", "WH-1000XM5", candidate("SONY", "wh1000xm5 Wireless"))


def test_is_match_accepts_the_brand_repeated_in_the_model() -> None:
    assert is_match("Apple", "AirPods Pro 2", candidate("Apple", "Apple AirPods Pro 2"))


def test_is_match_rejects_a_lookalike_model() -> None:
    assert not is_match("Sony", "WH-1000XM5", candidate("Sony", "WH-1000XM4"))


def test_top1_correct_uses_only_the_first_candidate() -> None:
    candidates = [candidate("Sony", "WH-1000XM4"), candidate("Sony", "WH-1000XM5")]
    assert not top1_correct("Sony", "WH-1000XM5", candidates)
    assert not top1_correct("Sony", "WH-1000XM5", [])
