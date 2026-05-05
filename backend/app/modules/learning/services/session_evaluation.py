import re
from difflib import SequenceMatcher

_RUSSIAN_STOPWORDS = {
    "и", "в", "во", "на", "с", "со", "к", "ко", "по", "под", "над", "от", "до", "из", "у",
    "за", "для", "о", "об", "про", "без", "после", "перед", "при", "через", "не", "ни", "же",
    "ли", "бы", "это", "этот", "эта", "эти", "тот", "та", "те", "мой", "моя", "мои", "твой",
    "твоя", "его", "ее", "их", "я", "ты", "он", "она", "они", "мы", "вы",
}


def normalize_answer(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _canonicalize_token(token: str) -> str:
    normalized = token.strip().lower().replace("ё", "е")
    if not normalized:
        return ""
    for suffix in (
        "ировались", "ировалась", "ировался", "ировать", "ированы", "ирована",
        "иями", "ями", "ами", "его", "ого", "ему", "ому", "ыми", "ими",
        "иях", "ах", "ях", "ой", "ей", "ою", "ею", "ом", "ем",
        "ешь", "ете", "ить", "ать", "ять", "еть", "уть",
        "ила", "ило", "или", "ена", "ено", "ены", "ешь", "ешься",
        "ал", "ала", "али", "ил", "ила", "или", "ел", "ела", "ели",
        "ия", "ья", "ию", "ью", "иям", "ьям", "ам", "ям",
        "а", "я", "у", "ю", "ы", "и", "е", "о",
    ):
        if normalized.endswith(suffix) and len(normalized) - len(suffix) >= 4:
            return normalized[: -len(suffix)]
    return normalized


def _canonicalize_tokens(tokens: list[str]) -> list[str]:
    return [_canonicalize_token(token) for token in tokens if _canonicalize_token(token)]


def answer_similarity_metrics(expected: str | None, user_answer: str | None) -> dict[str, float]:
    normalized_expected = normalize_answer(expected)
    normalized_user = normalize_answer(user_answer)
    expected_tokens = normalized_expected.split()
    user_tokens = normalized_user.split()
    expected_canonical_tokens = _canonicalize_tokens(expected_tokens)
    user_canonical_tokens = _canonicalize_tokens(user_tokens)

    if not normalized_expected or not normalized_user or not expected_tokens or not user_tokens:
        return {
            "text_similarity": 0.0,
            "token_recall": 0.0,
            "content_recall": 0.0,
            "canonical_token_recall": 0.0,
            "canonical_content_recall": 0.0,
        }

    expected_token_set = set(expected_tokens)
    user_token_set = set(user_tokens)
    expected_content = {token for token in expected_token_set if token not in _RUSSIAN_STOPWORDS}
    user_content = {token for token in user_token_set if token not in _RUSSIAN_STOPWORDS}
    expected_canonical_set = set(expected_canonical_tokens)
    user_canonical_set = set(user_canonical_tokens)
    expected_canonical_content = {
        token for token in expected_canonical_set if token not in _RUSSIAN_STOPWORDS
    }
    user_canonical_content = {
        token for token in user_canonical_set if token not in _RUSSIAN_STOPWORDS
    }

    return {
        "text_similarity": SequenceMatcher(None, normalized_expected, normalized_user).ratio(),
        "token_recall": len(expected_token_set & user_token_set) / max(1, len(expected_token_set)),
        "content_recall": len(expected_content & user_content) / max(1, len(expected_content)),
        "canonical_token_recall": len(expected_canonical_set & user_canonical_set) / max(1, len(expected_canonical_set)),
        "canonical_content_recall": len(expected_canonical_content & user_canonical_content) / max(1, len(expected_canonical_content)),
    }


def is_semantic_override_candidate(expected: str | None, user_answer: str | None) -> bool:
    metrics = answer_similarity_metrics(expected, user_answer)
    return (
        (
            metrics["text_similarity"] >= 0.72
            and metrics["token_recall"] >= 0.55
            and metrics["content_recall"] >= 0.6
        )
        or (
            metrics["canonical_token_recall"] >= 0.72
            and metrics["canonical_content_recall"] >= 0.78
        )
    )


def is_answer_correct(expected: str | None, user_answer: str | None) -> bool:
    normalized_expected = normalize_answer(expected)
    normalized_user = normalize_answer(user_answer)
    if not normalized_expected:
        return False
    if normalized_expected == normalized_user:
        return True

    expected_tokens = normalized_expected.split()
    user_tokens = normalized_user.split()
    if not expected_tokens or not user_tokens:
        return False

    # Single-word answers stay strict to avoid accidental false positives.
    if len(expected_tokens) == 1 or len(user_tokens) == 1:
        return False

    # For sentence translation tasks we allow close paraphrases:
    # small lexical variation with preserved overall meaning/structure.
    metrics = answer_similarity_metrics(expected, user_answer)

    return (
        (
            metrics["text_similarity"] >= 0.88
            and metrics["token_recall"] >= 0.7
            and metrics["content_recall"] >= 0.75
        )
        or (
            metrics["canonical_token_recall"] >= 0.8
            and metrics["canonical_content_recall"] >= 0.84
        )
    )
