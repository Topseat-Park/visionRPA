"""Abstract storage interface — swap local ↔ GCS transparently."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ABCStorage(ABC):
    @abstractmethod
    async def read_json(self, path: str) -> dict | None:
        ...

    @abstractmethod
    async def write_json(self, path: str, data: dict) -> None:
        ...

    @abstractmethod
    async def read_binary(self, path: str) -> bytes | None:
        ...

    @abstractmethod
    async def write_binary(self, path: str, data: bytes) -> None:
        ...

    @abstractmethod
    async def list_dir(self, path: str) -> list[str]:
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        ...

    @abstractmethod
    async def read_jsonl(self, path: str) -> list[dict]:
        ...

    @abstractmethod
    async def append_jsonl(self, path: str, record: dict) -> None:
        ...
