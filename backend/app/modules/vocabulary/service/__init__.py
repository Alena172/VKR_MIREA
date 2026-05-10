from app.modules.vocabulary.service.capture import capture_to_vocabulary
from app.modules.vocabulary.service.items import (
    create_item_with_ai,
    delete_item,
    get_definition_map_for_user,
    get_latest_item_by_lemma,
    get_translation_map_for_user,
    list_english_lemmas_for_user,
    list_items,
    list_user_items,
    queue_add_item,
    queue_add_item_from_capture,
    update_item,
)
from app.modules.vocabulary.service.lexicon import (
    ensure_seeded,
    import_entries,
    lookup_translation,
)
from app.modules.vocabulary.service.translation import (
    resolve_target_user_id,
    translate_for_user,
)

__all__ = [
    "capture_to_vocabulary",
    "create_item_with_ai",
    "delete_item",
    "ensure_seeded",
    "get_definition_map_for_user",
    "get_latest_item_by_lemma",
    "get_translation_map_for_user",
    "import_entries",
    "list_english_lemmas_for_user",
    "list_items",
    "list_user_items",
    "lookup_translation",
    "queue_add_item",
    "queue_add_item_from_capture",
    "resolve_target_user_id",
    "translate_for_user",
    "update_item",
]
