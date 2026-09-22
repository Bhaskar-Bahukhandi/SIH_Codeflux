from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fastapi import Depends

from app.core.config import Settings, get_settings


class MediaStorage(Protocol):
    def save(self, key: str, data: bytes) -> None: ...

    def delete(self, key: str) -> None: ...

    def path_for(self, key: str) -> Path: ...


class LocalMediaStorage:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if not key or Path(key).is_absolute():
            raise ValueError("Storage key must be a relative path.")

        candidate = (self.root / key).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Storage key escapes the media root.")
        return candidate

    def save(self, key: str, data: bytes) -> None:
        destination = self._resolve(key)
        destination.parent.mkdir(parents=True, exist_ok=True)

        temporary = destination.with_name(
            f".{destination.name}.{uuid4().hex}.tmp"
        )
        try:
            temporary.write_bytes(data)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    def path_for(self, key: str) -> Path:
        return self._resolve(key)


def get_media_storage(
    settings: Settings = Depends(get_settings),
) -> LocalMediaStorage:
    return LocalMediaStorage(settings.media_root)
