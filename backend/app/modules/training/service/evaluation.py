from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from difflib import SequenceMatcher

_RUSSIAN_STOPWORDS = {
    "и", "в", "во", "на", "с", "со", "к", "ко", "по", "под", "над", "от", "до", "из", "у",
    "за", "для", "о", "об", "про", "без", "после", "перед", "при", "через", "не", "ни", "же",
    "ли", "бы", "это", "этот", "эта", "эти", "тот", "та", "те", "мой", "моя", "мои", "твой",
    "твоя", "его", "ее", "их", "я", "ты", "он", "она", "они", "мы", "вы",
}
_WORD_RE = re.compile(r"^[a-z][a-z'-]{0,48}$")
_WHITESPACE_RE = re.compile(r"\s+")
_SCRAMBLE_PROMPT_PREFIX = "assemble the word from letters"
_DEFINITION_MATCH_PROMPT_PREFIX = "match each word with its definition"


def normalize_answer(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_text_fragment(value: str | None) -> str:
    return _WHITESPACE_RE.sub(" ", (value or "").strip()).casefold()


def normalize_word_candidate(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip().lower().strip(" \t\n\r\"'`.,!?;:()[]{}")
    if not candidate or not _WORD_RE.fullmatch(candidate):
        return None
    return candidate


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
    expected_canonical_content = {token for token in expected_canonical_set if token not in _RUSSIAN_STOPWORDS}
    user_canonical_content = {token for token in user_canonical_set if token not in _RUSSIAN_STOPWORDS}

    return {
        "text_similarity": SequenceMatcher(None, normalized_expected, normalized_user).ratio(),
        "token_recall": len(expected_token_set & user_token_set) / max(1, len(expected_token_set)),
        "content_recall": len(expected_content & user_content) / max(1, len(expected_content)),
        "canonical_token_recall": len(expected_canonical_set & user_canonical_set) / max(1, len(expected_canonical_set)),
        "canonical_content_recall": len(expected_canonical_content & user_canonical_content) / max(1, len(expected_canonical_content)),
    }


def is_semantic_override_candidate(expected: str | None, user_answer: str | None) -> bool:
    metrics = answer_similarity_metrics(expected, user_answer)
    normalized_expected = normalize_answer(expected)
    normalized_user = normalize_answer(user_answer)
    expected_tokens = normalized_expected.split()
    user_tokens = normalized_user.split()
    # Reject if length ratio is wildly off (< 40% or > 250% of expected length)
    if expected_tokens and user_tokens:
        ratio = len(user_tokens) / len(expected_tokens)
        if ratio < 0.4 or ratio > 2.5:
            return False
    return (
        (
            metrics["text_similarity"] >= 0.55
            and metrics["token_recall"] >= 0.3
            and metrics["content_recall"] >= 0.35
        )
        or (
            metrics["canonical_token_recall"] >= 0.5
            and metrics["canonical_content_recall"] >= 0.55
        )
        or metrics["text_similarity"] >= 0.75
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

    if len(expected_tokens) == 1 or len(user_tokens) == 1:
        return False

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


def detect_simple_exercise_type(
    *,
    exercise_type: str | None,
    prompt: str | None,
    expected_answer: str | None,
) -> str | None:
    normalized_type = normalize_text_fragment(exercise_type)
    if normalized_type in {"word_scramble", "word_definition_match"}:
        return normalized_type

    normalized_prompt = normalize_text_fragment(prompt)
    if normalized_prompt.startswith(_SCRAMBLE_PROMPT_PREFIX):
        return "word_scramble"
    if normalized_prompt.startswith(_DEFINITION_MATCH_PROMPT_PREFIX):
        return "word_definition_match"

    raw_expected = (expected_answer or "").strip()
    if raw_expected.startswith("[") and raw_expected.endswith("]"):
        try:
            parsed = json.loads(raw_expected)
        except Exception:
            return None
        if (
            isinstance(parsed, list)
            and parsed
            and all(
                isinstance(item, dict)
                and isinstance(item.get("word"), str)
                and isinstance(item.get("definition"), str)
                for item in parsed
            )
        ):
            return "word_definition_match"
    return None


def _normalize_scramble_answer(value: str | None) -> str:
    return re.sub(r"[^a-z]", "", (value or "").strip().lower())


def _parse_definition_match_pairs(raw_value: str | None) -> dict[str, str] | None:
    try:
        parsed = json.loads((raw_value or "").strip())
    except Exception:
        return None

    if not isinstance(parsed, list):
        return None

    result: dict[str, str] = {}
    for item in parsed:
        if not isinstance(item, dict):
            return None
        word = normalize_word_candidate(item.get("word"))
        definition = normalize_text_fragment(item.get("definition"))
        if not word or not definition:
            return None
        result[word] = definition
    return result or None


def evaluate_simple_exercise(
    *,
    expected_answer: str | None,
    user_answer: str | None,
    exercise_type: str,
) -> bool:
    if exercise_type == "word_scramble":
        return _normalize_scramble_answer(expected_answer) == _normalize_scramble_answer(user_answer)

    if exercise_type == "word_definition_match":
        expected_pairs = _parse_definition_match_pairs(expected_answer)
        user_pairs = _parse_definition_match_pairs(user_answer)
        return bool(expected_pairs and user_pairs and expected_pairs == user_pairs)

    return False


async def is_answer_correct_async(
    expected: str | None,
    user_answer: str | None,
    *,
    exercise_type: str | None = None,
    english_prompt: str | None = None,
    llm_check: Callable[..., Awaitable[bool]] | None = None,
) -> bool:
    """Hybrid check: fast string match first, LLM fallback for sentence translation."""
    if is_answer_correct(expected, user_answer):
        return True

    is_sentence_type = (exercise_type or "").startswith("sentence_translation")
    if not is_sentence_type or llm_check is None:
        return False

    # Only invoke LLM when answers are substantively different but possibly equivalent.
    if not is_semantic_override_candidate(expected, user_answer):
        return False

    try:
        return await llm_check(
            english_prompt=english_prompt or "",
            expected_answer=expected or "",
            user_answer=user_answer or "",
        )
    except Exception:
        return False


def extract_progress_word(
    *,
    target_word: str | None,
    prompt: str | None,
    expected_answer: str | None,
    vocabulary_words: set[str],
) -> str | None:
    normalized_target = normalize_word_candidate(target_word)
    if normalized_target and (not vocabulary_words or normalized_target in vocabulary_words):
        return normalized_target

    normalized_answer = normalize_word_candidate(expected_answer)
    if normalized_answer and (not vocabulary_words or normalized_answer in vocabulary_words):
        return normalized_answer

    if not prompt:
        return None

    after_colon = prompt.split(":", maxsplit=1)[-1]
    normalized_prompt_word = normalize_word_candidate(after_colon)
    if normalized_prompt_word and (not vocabulary_words or normalized_prompt_word in vocabulary_words):
        return normalized_prompt_word

    return None
