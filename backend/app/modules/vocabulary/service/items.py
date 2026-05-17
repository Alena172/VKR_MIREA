from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException

from app.core.application import application_access
from app.core.db import transaction
from app.modules.ai.facade import AIProviderUnavailableError
from app.modules.ai.facade import ai_facade as ai_service
from app.modules.ai.schemas import TranslateWithContextRequest
from app.modules.vocabulary.repository import VocabularyRepository
from app.modules.vocabulary.schemas import (
    TranslationResultDTO,
    VocabularyItemDTO,
    VocabularyItemUpdateMe,
)
from app.modules.vocabulary.service.definition import resolve_context_definition

if TYPE_CHECKING:
    from app.modules.graph.service.graph import GraphService
    from app.modules.review.service.srs import SRSService


def _to_dto(uv, entry) -> VocabularyItemDTO:
    return VocabularyItemDTO.from_model(uv, entry)


def _normalize_english_lemma(text: str) -> str:
    return text.strip().split()[0].lower()


def _normalize_translation(text: str) -> str:
    value = text.strip()
    if value.startswith("[RU]"):
        value = value.replace("[RU]", "", 1).strip()
    return value or "перевод не найден"


def _build_translation_note(provider_note: str) -> str:
    normalized = provider_note.strip().lower()
    if normalized.startswith("local_heuristic"):
        return f"Использован локальный эвристический перевод ({provider_note})"
    if normalized.startswith("ai_disambiguation:"):
        return f"Использована AI-дизамбигуация ({provider_note})"
    if normalized.startswith("ai_translation:"):
        return f"Использован AI-перевод ({provider_note})"
    if normalized.startswith("glossary"):
        return f"Использован перевод из глоссария ({provider_note})"
    return f"Перевод выполнен ({provider_note})"


class VocabularyService:
    def __init__(
        self,
        repo: VocabularyRepository = Depends(),
    ) -> None:
        self._repo = repo
        self._graph_service: GraphService | None = None
        self._srs_service: SRSService | None = None

    def _graph(self) -> GraphService:
        if self._graph_service is None:
            from app.modules.graph.repository import GraphRepository
            from app.modules.graph.service.graph import GraphService
            from app.modules.identity.repository import IdentityRepository
            from app.modules.identity.service import IdentityService
            self._graph_service = GraphService(
                GraphRepository(self._repo._db),
                IdentityService(IdentityRepository(self._repo._db)),
            )
        return self._graph_service

    def _srs(self) -> SRSService:
        if self._srs_service is None:
            from app.modules.identity.repository import IdentityRepository
            from app.modules.identity.service import IdentityService
            from app.modules.review.repository import ReviewRepository
            from app.modules.review.service.scoring import RecommendationScoringService
            from app.modules.review.service.srs import SRSService
            review_repo = ReviewRepository(self._repo._db)
            self._srs_service = SRSService(
                repo=review_repo,
                scoring_service=RecommendationScoringService(review_repo=review_repo),
                identity_service=IdentityService(IdentityRepository(self._repo._db)),
                vocabulary_service=self,
            )
        return self._srs_service

    # ------------------------------------------------------------------
    # Словарные элементы
    # ------------------------------------------------------------------

    def list_items(
        self,
        *,
        requested_user_id: int | None,
        current_user_id: int,
    ) -> list[VocabularyItemDTO]:
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=requested_user_id,
            current_user_id=current_user_id,
        )
        return [_to_dto(uv, entry) for uv, entry in self._repo.list_user_vocabulary(user_id=target_user_id)]

    def list_user_items(self, *, user_id: int) -> list[VocabularyItemDTO]:
        return [_to_dto(uv, entry) for uv, entry in self._repo.list_user_vocabulary(user_id=user_id)]

    async def create_item_with_ai(
        self,
        *,
        user_id: int,
        english_lemma: str,
        russian_translation: str,
        source_sentence: str | None,
        source_url: str | None,
    ) -> VocabularyItemDTO:
        application_access.get_user_or_404(user_id=user_id, db=self._repo._db)

        normalized_lemma = english_lemma.strip().lower()
        normalized_translation = russian_translation.strip()
        normalized_sentence = source_sentence.strip() if source_sentence else None
        normalized_url = source_url.strip() if source_url else None

        definition_resolution = await resolve_context_definition(
            repo=self._repo,
            english_lemma=normalized_lemma,
            russian_translation=normalized_translation,
            source_sentence=normalized_sentence,
        )

        with transaction(self._repo._db):
            topic_cluster_id = self._graph().register_word_topic(
                user_id=user_id,
                english_lemma=normalized_lemma,
                russian_translation=normalized_translation,
                context_definition_ru=definition_resolution.context_definition,
                source_sentence=normalized_sentence,
            )
            entry, _ = self._repo.get_or_create_dictionary_entry(
                english_lemma=normalized_lemma,
                russian_translation=normalized_translation,
                context_definition_ru=definition_resolution.context_definition,
                topic_cluster_id=topic_cluster_id,
            )
            uv, _ = self._repo.add_to_user_vocabulary(
                user_id=user_id,
                entry_id=entry.id,
                source_sentence=normalized_sentence,
                source_url=normalized_url,
            )
            self._srs().ensure_word_progress_entry(user_id=user_id, vocabulary_id=uv.id)

        return _to_dto(uv, entry)

    def update_item(
        self,
        *,
        item_id: int,
        payload: VocabularyItemUpdateMe,
        current_user_id: int,
    ) -> VocabularyItemDTO:
        row = self._repo.get_user_vocabulary_item(user_id=current_user_id, item_id=item_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Vocabulary item not found")
        uv, entry = row
        self._repo.update_user_vocabulary_item(
            uv,
            source_sentence=payload.source_sentence,
            source_url=payload.source_url,
        )
        return _to_dto(uv, entry)

    def delete_item(self, *, item_id: int, current_user_id: int) -> dict[str, bool]:
        row = self._repo.get_user_vocabulary_item(user_id=current_user_id, item_id=item_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Vocabulary item not found")
        uv, _ = row
        with transaction(self._repo._db):
            self._repo.delete_user_vocabulary_item(uv)
        return {"deleted": True}

    # ------------------------------------------------------------------
    # Capture-пайплайн
    # ------------------------------------------------------------------

    async def _generate_capture_ai_data(
        self,
        *,
        source_sentence: str | None,
        english_lemma: str,
        cefr_level: str,
    ) -> tuple[str, str, str | None]:
        # Многозначные слова → AI (LibreTranslate не учитывает контекст для омонимов).
        # Однозначные слова → LibreTranslate/локальный перевод через translate_with_context_async
        # (там LibreTranslate идёт первым, AI — только как запасной).
        # Общий словарь не используется как источник перевода — только для сохранения:
        # если полученный перевод совпадает с уже существующей записью, она переиспользуется.
        force_ai = ai_service.is_ambiguous_word(english_lemma)
        contextual_response = await ai_service.translate_with_context_async(
            TranslateWithContextRequest(
                text=english_lemma,
                cefr_level=cefr_level,
                source_context=source_sentence,
                force_ai=force_ai,
            )
        )
        russian_translation = _normalize_translation(contextual_response.translated_text)
        return russian_translation, contextual_response.provider_note, source_sentence

    async def capture_to_vocabulary(
        self,
        *,
        user_id: int,
        selected_text: str,
        source_url: str | None,
        source_sentence: str | None,
        force_new_vocabulary_item: bool,
    ) -> tuple[VocabularyItemDTO, bool]:
        user = application_access.get_user_or_404(user_id=user_id, db=self._repo._db)
        normalized_url = source_url.strip() if source_url else None
        normalized_sentence = source_sentence.strip() if source_sentence else None
        english_lemma = _normalize_english_lemma(selected_text)

        # Fast-path: reuse existing entry only when there is no context sentence.
        # With context we must translate first — the new sentence may reveal a different sense.
        if not force_new_vocabulary_item and not normalized_sentence:
            existing_row = self._repo.get_latest_vocabulary_item_by_lemma(
                user_id=user_id, english_lemma=english_lemma
            )
            if existing_row is not None:
                uv, entry = existing_row
                with transaction(self._repo._db):
                    self._srs().ensure_word_progress_entry(user_id=user_id, vocabulary_id=uv.id)
                return _to_dto(uv, entry), False

        russian_translation, _note, semantic_sentence = await self._generate_capture_ai_data(
            source_sentence=normalized_sentence,
            english_lemma=english_lemma,
            cefr_level=user.cefr_level,
        )
        definition_resolution = await resolve_context_definition(
            repo=self._repo,
            english_lemma=english_lemma,
            russian_translation=russian_translation,
            source_sentence=semantic_sentence,
        )

        with transaction(self._repo._db):
            existing_row = self._repo.get_latest_vocabulary_item_by_lemma(
                user_id=user_id,
                english_lemma=english_lemma,
            )
            # Переиспользуем запись только при совпадении перевода, то есть смысла.
            # Если перевод другой, считаем это новым контекстом/значением и создаем новую запись.
            same_sense = (
                existing_row is not None
                and not force_new_vocabulary_item
                and existing_row[1].russian_translation == russian_translation
            )

            topic_cluster_id = self._graph().register_word_topic(
                user_id=user_id,
                english_lemma=english_lemma,
                russian_translation=russian_translation,
                context_definition_ru=definition_resolution.context_definition,
                source_sentence=semantic_sentence,
            )

            if same_sense:
                uv, entry = existing_row
            else:
                entry, _ = self._repo.get_or_create_dictionary_entry(
                    english_lemma=english_lemma,
                    russian_translation=russian_translation,
                    context_definition_ru=definition_resolution.context_definition,
                    topic_cluster_id=topic_cluster_id,
                )
                uv, _ = self._repo.add_to_user_vocabulary(
                    user_id=user_id,
                    entry_id=entry.id,
                    source_sentence=normalized_sentence,
                    source_url=normalized_url,
                )

            self._srs().ensure_word_progress_entry(user_id=user_id, vocabulary_id=uv.id)

        return _to_dto(uv, entry), not same_sense

    # ------------------------------------------------------------------
    # Перевод
    # ------------------------------------------------------------------

    async def translate_for_user(
        self,
        *,
        user_id: int,
        text: str,
        source_context: str | None,
    ) -> TranslationResultDTO:
        user_model = self._graph()._identity_service.get_user_or_404(user_id=user_id)

        # Многозначные слова → AI, однозначные → LibreTranslate (AI как запасной).
        # Глоссарий пользователя НЕ передаём для самого переводимого слова:
        # это предотвращает навязывание ранее сохранённого смысла при другом контексте.
        lemma = text.strip().lower()
        force_ai = ai_service.is_ambiguous_word(text)
        glossary_items = [
            {
                "english_term": item.english_lemma,
                "russian_translation": item.russian_translation,
                "source_sentence": item.source_sentence,
            }
            for item in self.list_user_items(user_id=user_id)[:50]
            if item.english_lemma.lower() != lemma
        ]

        try:
            ai_response = await ai_service.translate_with_context_async(
                TranslateWithContextRequest(
                    text=text,
                    cefr_level=user_model.cefr_level,
                    source_context=source_context,
                    glossary=glossary_items,
                    force_ai=force_ai,
                )
            )
        except AIProviderUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return TranslationResultDTO(
            translated_text=ai_response.translated_text,
            note=_build_translation_note(ai_response.provider_note),
        )
