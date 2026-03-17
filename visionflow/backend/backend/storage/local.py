"""Local filesystem storage implementation."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import aiofiles

from .base import ABCStorage


class LocalStorage(ABCStorage):
    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        return self._base / path

    async def read_json(self, path: str) -> dict | None:
        p = self._resolve(path)
        if not p.exists():
            return None
        async with aiofiles.open(p, "r", encoding="utf-8") as f:
            content = await f.read()
        return json.loads(content)

    async def write_json(self, path: str, data: dict) -> None:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_path = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        try:
            async with aiofiles.open(tmp_fd, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False, default=str))
            Path(tmp_path).replace(p)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    async def read_binary(self, path: str) -> bytes | None:
        p = self._resolve(path)
        if not p.exists():
            return None
        async with aiofiles.open(p, "rb") as f:
            return await f.read()

    async def write_binary(self, path: str, data: bytes) -> None:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(p, "wb") as f:
            await f.write(data)

    async def list_dir(self, path: str) -> list[str]:
        p = self._resolve(path)
        if not p.exists():
            return []
        return sorted([item.name for item in p.iterdir()])

    async def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    async def delete(self, path: str) -> None:
        p = self._resolve(path)
        if p.is_file():
            p.unlink(missing_ok=True)
        elif p.is_dir():
            import shutil
            shutil.rmtree(p, ignore_errors=True)

    async def read_jsonl(self, path: str) -> list[dict]:
        p = self._resolve(path)
        if not p.exists():
            return []
        async with aiofiles.open(p, "r", encoding="utf-8") as f:
            content = await f.read()
        lines = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                lines.append(json.loads(line))
        return lines

    async def append_jsonl(self, path: str, record: dict) -> None:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(p, "a", encoding="utf-8") as f:
            await f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
