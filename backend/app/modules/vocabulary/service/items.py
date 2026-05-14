from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException

from app.celery_app import enqueue_task
from app.core.application import AsyncTaskResponse, application_access
from app.core.db import transaction
from app.modules.ai.facade import AIProviderUnavailableError
from app.modules.ai.facade import ai_facade as ai_service
from app.modules.ai.schemas import TranslateWithContextRequest
from app.modules.vocabulary.repository import VocabularyRepository
from app.modules.vocabulary.schemas import (
    TranslationResultDTO,
    VocabularyFromCaptureRequest,
    VocabularyItemCreate,
    VocabularyItemDTO,
    VocabularyItemUpdateMe,
)
from app.modules.vocabulary.service.definition import resolve_context_definition
from app.modules.vocabulary.service.lexicon import lookup_translation

if TYPE_CHECKING:
    from app.modules.graph.service.graph import GraphService
    from app.modules.review.service.srs import SRSService

_ENGLISH_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _to_dto(uv, entry) -> VocabularyItemDTO:
    return VocabularyItemDTO.from_model(uv, entry)


def _normalize_english_lemma(text: str) -> str:
    return text.strip().split()[0].lower()


def _normalize_translation(text: str) -> str:
    value = text.strip()
    if value.startswith("[RU]"):
        value = value.replace("[RU]", "", 1).strip()
    return value or "перевод не найден"


def _english_tokens(text: str | None) -> list[str]:
    return [token.lower() for token in _ENGLISH_TOKEN_RE.findall(text or "")]


def _is_single_word_capture(text: str) -> bool:
    return len(_english_tokens(text)) == 1


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


def _is_single_token(text: str) -> bool:
    return len(text.strip().split()) == 1


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

    def queue_add_item(
        self,
        *,
        payload: VocabularyItemCreate,
        current_user_id: int,
    ) -> AsyncTaskResponse:
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=payload.user_id,
            current_user_id=current_user_id,
        )
        application_access.get_user_or_404(user_id=target_user_id, db=self._repo._db)

        from app.tasks.vocabulary_tasks import add_word_with_ai

        task = enqueue_task(
            add_word_with_ai,
            owner_user_id=current_user_id,
            kwargs={
                "user_id": target_user_id,
                "english_lemma": payload.english_lemma.strip().lower(),
                "russian_translation": payload.russian_translation.strip(),
                "source_sentence": payload.source_sentence.strip() if payload.source_sentence else None,
                "source_url": payload.source_url.strip() if payload.source_url else None,
            },
        )
        return AsyncTaskResponse(task_id=task.id)

    def queue_add_item_from_capture(
        self,
        *,
        payload: VocabularyFromCaptureRequest,
        current_user_id: int,
    ) -> AsyncTaskResponse:
        target_user_id = application_access.resolve_target_user_id(
            requested_user_id=payload.user_id,
            current_user_id=current_user_id,
        )
        application_access.get_user_or_404(user_id=target_user_id, db=self._repo._db)

        from app.tasks.vocabulary_tasks import capture_to_vocabulary_task

        task = enqueue_task(
            capture_to_vocabulary_task,
            owner_user_id=current_user_id,
            kwargs={
                "user_id": target_user_id,
                "selected_text": payload.selected_text,
                "source_url": payload.source_url,
                "source_sentence": payload.source_sentence,
                "force_new_vocabulary_item": payload.force_new_vocabulary_item,
            },
        )
        return AsyncTaskResponse(task_id=task.id)

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
        selected_text: str,
        source_sentence: str | None,
        english_lemma: str,
        cefr_level: str,
    ) -> tuple[str, str, str | None]:
        # Быстрый локальный поиск делаем только без контекстного предложения:
        # если контекст есть, пользователь может сохранять конкретный смысл
        # слова, и общий словарный перевод окажется неверным.
        if _is_single_word_capture(selected_text) and not source_sentence:
            shared_translation = self._repo.find_shared_translation(english_lemma=english_lemma)
            fast_translation = (
                shared_translation
                or lookup_translation(repo=self._repo, english_lemma=english_lemma)
                or ai_service.fast_translate_single_word(english_lemma)
            )
            if fast_translation:
                return (
                    _normalize_translation(fast_translation),
                    "fast_local_word_translation; local_definition",
                    None,
                )

        contextual_response = await ai_service.translate_with_context_async(
            TranslateWithContextRequest(
                text=english_lemma,
                cefr_level=cefr_level,
                source_context=source_sentence,
            )
        )
        russian_translation = _normalize_translation(contextual_response.translated_text)
        translation_note = contextual_response.provider_note
        semantic_sentence = source_sentence

        return russian_translation, translation_note, semantic_sentence

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

        russian_translation, _note, semantic_sentence = await self._generate_capture_ai_data(
            selected_text=selected_text,
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

        if _is_single_token(text) and not source_context:
            shared = self._repo.find_shared_translation(english_lemma=text.strip())
            if shared:
                return TranslationResultDTO(
                    translated_text=shared,
                    note=_build_translation_note("glossary:shared_dictionary"),
                )

        try:
            ai_response = await ai_service.translate_with_context_async(
                TranslateWithContextRequest(
                    text=text,
                    cefr_level=user_model.cefr_level,
                    source_context=source_context,
                    glossary=[
                        {
                            "english_term": item.english_lemma,
                            "russian_translation": item.russian_translation,
                            "source_sentence": item.source_sentence,
                        }
                        for item in self.list_user_items(user_id=user_id)[:50]
                    ],
                )
            )
        except AIProviderUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return TranslationResultDTO(
            translated_text=ai_response.translated_text,
            note=_build_translation_note(ai_response.provider_note),
        )
