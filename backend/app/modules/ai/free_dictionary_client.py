"""Клиент Free Dictionary API (https://dictionaryapi.dev).

Стратегия:
1. Получаем все definitions для слова.
2. Скорим каждое определение по совпадению с russian_translation
   (через словарь EN→ключевых слов смысла) и source_sentence.
3. Если лучший score >= порога → возвращаем определение (экономим токены).
4. Если слово многозначное и score низкий → возвращаем None → fallback на AI.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

_BASE_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
_TIMEOUT = 4.0

# Минимальный score, при котором доверяем найденному определению
_SCORE_THRESHOLD = 0.20

# Слово считается многозначным если у него >= N различных частей речи.
# Порог 2: любое слово, которое может быть и существительным, и глаголом
# (или прилагательным и наречием), отправляется в AI для дизамбигуации.
_POLYSEMY_POS_THRESHOLD = 2

# Слова с сильно различными значениями при малом кол-ве POS → принудительно в AI
_FORCE_AI_WORDS = frozenset({
    # A
    "act", "address", "age", "air", "arm", "arms",
    # B
    "back", "ball", "band", "bank", "bar", "bark", "base", "bat",
    "bear", "beat", "bed", "bill", "bit", "blow", "board", "bolt",
    "bond", "book", "bore", "bound", "bow", "box", "break", "brief",
    "bright", "broad", "bug", "burn", "book",
    # C
    "call", "can", "cap", "care", "carry", "case", "cast", "catch",
    "charge", "check", "chip", "class", "clear", "close", "cold",
    "color", "colour", "content", "cool", "count", "course", "cover",
    "crack", "craft", "cross", "current", "cut",
    # D
    "date", "deal", "deck", "deep", "degree", "deposit", "draw",
    "dress", "drift", "drive", "drop", "dry", "dump",
    # E
    "ease", "even", "express",
    # F
    "face", "fair", "fall", "fast", "fault", "feel", "field", "few",
    "figure", "file", "fine", "fire", "fit", "fix", "flat", "fly",
    "fold", "force", "form", "found", "free", "front",
    # G
    "gain", "game", "gear", "get", "give", "go", "grade", "grain",
    "grant", "grave", "grip", "gross", "ground",
    # H
    "hand", "hard", "head", "heat", "hide", "hit", "hold", "hook",
    "host",
    # I
    "issue",
    # J
    "jam", "joint",
    # K
    "key", "kind",
    # L
    "land", "last", "lay", "lead", "lean", "left", "letter", "level",
    "lie", "light", "like", "line", "live", "log", "long", "look",
    "lot", "low",
    # M
    "mark", "match", "matter", "mean", "measure", "meet", "mine",
    "miss", "model", "models", "mount", "move",
    # N
    "nail", "note",
    # O
    "object", "order", "over",
    # P
    "pack", "page", "park", "part", "pass", "patch", "pay", "pick",
    "pitch", "plain", "plan", "plant", "play", "plot", "point",
    "pool", "pop", "port", "post", "pound", "press", "prime",
    "produce", "project", "pull",
    # R
    "raise", "range", "rank", "rate", "reach", "read", "record",
    "refuse", "release", "rest", "return", "right", "ring", "rise",
    "rock", "roll", "round", "row", "run",
    # S
    "saw", "scale", "screen", "seal", "season", "second", "sense",
    "serve", "set", "settle", "shade", "shape", "share", "shift",
    "shoot", "short", "show", "side", "sight", "sign", "sink",
    "slip", "smooth", "sort", "sound", "spare", "spell", "spin",
    "split", "spot", "spread", "spring", "square", "stamp", "stand",
    "state", "stay", "stem", "step", "stick", "still", "stock",
    "store", "strain", "strike", "string", "strip", "suit", "switch",
    "swing",
    # T
    "take", "tank", "tape", "tear", "term", "think", "throw",
    "tie", "tip", "top", "touch", "train", "treat", "trip",
    "trust", "turn",
    # U
    "use",
    # V
    "value", "view",
    # W
    "wake", "walk", "ward", "waste", "watch", "wave", "wear",
    "well", "will", "wind", "work",
    # Y
    "yard",
})

_EN_STOP = {
    "the", "a", "an", "of", "to", "in", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall",
    "and", "or", "but", "if", "on", "at", "by", "for", "with",
    "this", "that", "these", "those", "it", "its",
}

# Грубый словарик часто встречающихся русских слов → английские эквиваленты для scoring
# Позволяет немного учесть перевод при выборе определения
_RU_EN_HINTS: dict[str, list[str]] = {
    "книга": ["book", "volume", "publication", "text"],
    "бронировать": ["reserve", "booking", "reservation", "schedule"],
    "свет": ["light", "illumination", "brightness", "lamp"],
    "лёгкий": ["light", "easy", "simple", "gentle"],
    "бежать": ["run", "running", "jog", "sprint"],
    "работать": ["work", "run", "operate", "function"],
    "смотреть": ["watch", "look", "see", "observe"],
    "часы": ["watch", "clock", "timepiece"],
    "справедливый": ["fair", "just", "equitable"],
    "ярмарка": ["fair", "market", "festival"],
    "банк": ["bank", "financial", "institution"],
    "берег": ["bank", "shore", "riverbank"],
    "завод": ["plant", "factory", "mill"],
    "растение": ["plant", "vegetation", "flora"],
    "дата": ["date", "calendar", "day"],
    "свидание": ["date", "meeting", "appointment"],
    "финик": ["date", "fruit"],
    "батарея": ["battery", "cell", "charge"],
    "удар": ["bat", "hit", "strike", "blow"],
    "летучая мышь": ["bat", "mammal"],
    "палка": ["bat", "stick", "club"],
}

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]{1,}")


def _en_tokens(text: str | None) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _EN_STOP}


@dataclass(frozen=True)
class DictApiDefinition:
    part_of_speech: str
    definition: str
    example: str | None
    synonyms: list[str]


async def fetch_definitions(word: str) -> list[DictApiDefinition] | None:
    """Возвращает список определений или None при ошибке/отсутствии слова."""
    url = _BASE_URL.format(word=word.strip().lower())
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None

    results: list[DictApiDefinition] = []
    for entry in data:
        for meaning in entry.get("meanings", []):
            pos = meaning.get("partOfSpeech", "")
            syns = meaning.get("synonyms", [])
            for d in meaning.get("definitions", []):
                results.append(DictApiDefinition(
                    part_of_speech=pos,
                    definition=d.get("definition", ""),
                    example=d.get("example"),
                    synonyms=syns + d.get("synonyms", []),
                ))
    return results or None


def _count_distinct_pos(definitions: list[DictApiDefinition]) -> int:
    return len({d.part_of_speech for d in definitions if d.part_of_speech})


# Глаголы в русском обычно заканчиваются на ть/ться/чь
_RU_VERB_RE = re.compile(r"[а-яё](ть|ться|чь|чься|ить|ать|овать|евать)$")


def _expected_pos(russian_translation: str) -> str | None:
    """Грубое определение ожидаемой части речи по форме русского слова."""
    ru = russian_translation.strip().lower()
    if _RU_VERB_RE.search(ru):
        return "verb"
    return None


def _score_definition(
    defn: DictApiDefinition,
    *,
    russian_translation: str,
    source_sentence: str | None,
) -> float:
    ru_lower = russian_translation.strip().lower()
    score = 0.0

    # 1. Подсказки по переводу: ищем EN-hints для русского слова
    hints = _RU_EN_HINTS.get(ru_lower, [])
    def_tokens = _en_tokens(defn.definition)
    syn_lower = [s.lower() for s in defn.synonyms]
    if hints:
        hit = sum(1 for h in hints if h in def_tokens or h in syn_lower)
        score += 0.45 * min(hit / len(hints), 1.0)

    # 2. Часть речи совпадает с ожидаемой по переводу
    expected = _expected_pos(russian_translation)
    if expected and defn.part_of_speech == expected:
        score += 0.15

    # 3. Контекстное предложение: overlap токенов definition + example
    if source_sentence:
        ctx_tokens = _en_tokens(source_sentence)
        candidate_tokens = def_tokens | _en_tokens(defn.example)
        if ctx_tokens and candidate_tokens:
            overlap = len(ctx_tokens & candidate_tokens) / max(1, len(ctx_tokens))
            score += 0.40 * overlap

    return min(score, 1.0)


@dataclass(frozen=True)
class DictApiResult:
    definition: str
    score: float
    is_polysemous: bool


async def lookup_definition(
    word: str,
    *,
    russian_translation: str,
    source_sentence: str | None,
) -> DictApiResult | None:
    """Основная точка входа.

    Возвращает DictApiResult если нашли подходящее определение,
    None если слово не найдено или confidence низкий (→ нужен AI).
    """
    definitions = await fetch_definitions(word)
    if not definitions:
        return None

    is_polysemous = _count_distinct_pos(definitions) >= _POLYSEMY_POS_THRESHOLD

    # Известные омонимы и слова с принципиально разными значениями → сразу AI
    if word.strip().lower() in _FORCE_AI_WORDS:
        return None

    # Многозначное слово: Free Dictionary (Wiktionary) плохо справляется —
    # слишком много редких значений, порядок не по частоте → сразу AI
    if is_polysemous:
        return None

    expected_pos = _expected_pos(russian_translation)
    best_def: DictApiDefinition | None = None
    best_score = 0.0
    first_by_pos: DictApiDefinition | None = None

    for d in definitions:
        s = _score_definition(d, russian_translation=russian_translation, source_sentence=source_sentence)
        if s > best_score:
            best_score = s
            best_def = d
        if first_by_pos is None and (expected_pos is None or d.part_of_speech == expected_pos):
            first_by_pos = d

    if best_score >= _SCORE_THRESHOLD and best_def is not None:
        candidate = best_def
    elif first_by_pos is not None:
        # Однозначное слово — берём первое определение нужной части речи
        candidate = first_by_pos
        best_score = _SCORE_THRESHOLD
    else:
        return None

    text = candidate.definition.strip()
    if not text:
        return None
    if text[-1] not in ".!?":
        text += "."
    return DictApiResult(definition=text, score=best_score, is_polysemous=is_polysemous)
