from __future__ import annotations

from app.modules.capture.repository import capture_repository

__all__ = [
    "capture_public_api",
]


class CapturePublicApi:
    create = staticmethod(capture_repository.create)
    list_items = staticmethod(capture_repository.list_items)


capture_public_api = CapturePublicApi()
