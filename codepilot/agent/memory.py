from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb

from codepilot.indexer.repo import HashEmbedding


@dataclass
class ShortTermMemory:
    path: Path
    window_size: int = 6
    max_chars: int = 4000
    summary: str = ""
    turns: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls, memory_path: Path, window_size: int, max_chars: int) -> "ShortTermMemory":
        path = memory_path / "short_term.json"
        if not path.exists():
            return cls(path=path, window_size=window_size, max_chars=max_chars)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            path=path,
            window_size=window_size,
            max_chars=max_chars,
            summary=str(data.get("summary", "")),
            turns=list(data.get("turns", [])),
        )

    def add_turn(self, role: str, content: str) -> None:
        self.turns.append(
            {
                "role": role,
                "content": content[: self.max_chars],
                "created_at": datetime.utcnow().isoformat(),
            }
        )
        self.compress()

    def compress(self) -> None:
        if len(self.turns) <= self.window_size:
            return
        archived = self.turns[: -self.window_size]
        self.turns = self.turns[-self.window_size :]
        archive_text = "\n".join(f"{item['role']}: {item['content']}" for item in archived)
        merged = (self.summary + "\n" + archive_text).strip()
        self.summary = merged[-self.max_chars :]

    def render(self) -> str:
        parts = []
        if self.summary:
            parts.append("Compressed summary:\n" + self.summary)
        if self.turns:
            turns = "\n".join(f"{item['role']}: {item['content']}" for item in self.turns)
            parts.append("Recent window:\n" + turns)
        return "\n\n".join(parts)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"summary": self.summary, "turns": self.turns}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class LongTermMemory:
    def __init__(self, memory_path: Path, repo_path: Path) -> None:
        self.memory_path = memory_path
        self.repo_path = repo_path.resolve()
        self.memory_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.memory_path))
        name = "memory_" + hashlib.sha1(str(self.repo_path).encode()).hexdigest()[:16]
        self.collection = self.client.get_or_create_collection(name=name, embedding_function=HashEmbedding())

    def add(self, task_id: str, user_request: str, content: str) -> None:
        text = f"Request:\n{user_request}\n\nResult:\n{content}"
        doc_id = hashlib.sha1(f"{task_id}:{text}".encode("utf-8", errors="ignore")).hexdigest()
        self.collection.upsert(
            ids=[doc_id],
            documents=[text[:12000]],
            metadatas=[
                {
                    "task_id": task_id,
                    "repo_path": str(self.repo_path),
                    "created_at": datetime.utcnow().isoformat(),
                }
            ],
        )

    def search(self, query: str, limit: int = 4) -> list[dict[str, Any]]:
        if self.collection.count() == 0:
            return []
        result = self.collection.query(query_texts=[query], n_results=limit)
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        return [
            {
                "content": str(doc)[:3000],
                "task_id": str(meta.get("task_id", "")),
                "created_at": str(meta.get("created_at", "")),
            }
            for doc, meta in zip(docs, metas)
        ]
