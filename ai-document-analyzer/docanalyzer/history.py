"""Persistent chat history stored as JSON files. No Streamlit dependency."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ChatStore:
    def __init__(self, directory: str | Path = "chat_history"):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.dir / "index.json"

    # ---------------------------------------------------------------- internals
    def _read_index(self) -> list[dict]:
        if not self.index_file.exists():
            return []
        try:
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

    def _write_index(self, index: list[dict]) -> None:
        self.index_file.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def _path(self, chat_id: str) -> Path:
        # chat ids are generated here, but never trust them as paths
        return self.dir / f"{Path(chat_id).name}.json"

    @staticmethod
    def _title(messages: list[dict]) -> str:
        for m in messages:
            if m.get("role") == "user":
                text = m.get("content", "").strip().replace("\n", " ")
                return text[:50] + ("..." if len(text) > 50 else "") or "New chat"
        return "New chat"

    # ------------------------------------------------------------------ public
    def save(self, chat_id: str | None, messages: list[dict], file_names: list[str]) -> str | None:
        if not messages:
            return chat_id
        index = self._read_index()
        entry = next((c for c in index if c["id"] == chat_id), None) if chat_id else None

        if entry is None:
            chat_id = uuid.uuid4().hex[:12]
            entry = {"id": chat_id, "title": self._title(messages), "created_at": _now()}
            index.insert(0, entry)
        elif not entry.get("custom_title"):
            entry["title"] = self._title(messages)

        entry.update(updated_at=_now(), message_count=len(messages), file_count=len(file_names))
        payload = {**entry, "messages": messages, "file_names": file_names}
        self._path(chat_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._write_index(index)
        return chat_id

    def load(self, chat_id: str) -> dict | None:
        path = self._path(chat_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def delete(self, chat_id: str) -> None:
        self._write_index([c for c in self._read_index() if c["id"] != chat_id])
        path = self._path(chat_id)
        if path.exists():
            path.unlink()

    def rename(self, chat_id: str, title: str) -> None:
        index = self._read_index()
        for c in index:
            if c["id"] == chat_id:
                c["title"], c["custom_title"] = title.strip() or c["title"], True
        self._write_index(index)

    def list(self) -> list[dict]:
        return sorted(self._read_index(), key=lambda c: c.get("updated_at", ""), reverse=True)

    def search(self, query: str) -> list[dict]:
        q = query.lower().strip()
        if not q:
            return self.list()
        hits = []
        for c in self.list():
            if q in c["title"].lower():
                hits.append(c)
                continue
            data = self.load(c["id"]) or {}
            if any(q in m.get("content", "").lower() for m in data.get("messages", [])):
                hits.append(c)
        return hits


def relative_time(iso: str) -> str:
    diff = datetime.now() - datetime.fromisoformat(iso)
    if diff.days > 0:
        return f"{diff.days}d ago"
    if diff.seconds >= 3600:
        return f"{diff.seconds // 3600}h ago"
    if diff.seconds >= 60:
        return f"{diff.seconds // 60}m ago"
    return "just now"
