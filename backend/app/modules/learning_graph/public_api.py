from __future__ import annotations

from app.modules.learning_graph.application_service import learning_graph_application_service

__all__ = [
    "learning_graph_public_api",
]


class LearningGraphPublicApi:
    list_recommendation_items = staticmethod(learning_graph_application_service.list_recommendation_items)
    register_vocabulary_semantics = staticmethod(learning_graph_application_service.register_vocabulary_semantics)
    register_mistake = staticmethod(learning_graph_application_service.register_mistake)
    list_word_anchors = staticmethod(learning_graph_application_service.list_word_anchors)


learning_graph_public_api = LearningGraphPublicApi()
