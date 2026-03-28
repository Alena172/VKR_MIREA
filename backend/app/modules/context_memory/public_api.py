from __future__ import annotations

from app.modules.context_memory.application_service import (
    WordProgressUpdate,
    context_memory_application_service,
)

__all__ = [
    "WordProgressUpdate",
    "context_memory_public_api",
]


class ContextMemoryPublicApi:
    get_effective_cefr_level = staticmethod(context_memory_application_service.get_effective_cefr_level)
    ensure_word_progress_entry = staticmethod(context_memory_application_service.ensure_word_progress_entry)
    update_learning_progress = staticmethod(context_memory_application_service.update_learning_progress)


context_memory_public_api = ContextMemoryPublicApi()
