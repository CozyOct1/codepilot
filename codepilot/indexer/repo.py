from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings


TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".css",
    ".html",
    ".sh",
}


class HashEmbedding(EmbeddingFunction[Documents]):
    """Deterministic lightweight embeddings for local/offline indexing."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def name() -> str:
        return "codepilot_hash_embedding"

    def get_config(self) -> dict[str, object]:
        return {}

    @staticmethod
    def build_from_config(config: dict[str, object]) -> "HashEmbedding":
        return HashEmbedding()

    def __call__(self, input: Documents) -> Embeddings:
        vectors: list[list[float]] = []
        for text in input:
            digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
            vec = [0.0] * 64
            for i, byte in enumerate(digest * 2):
                vec[i] = (byte / 255.0) - 0.5
            vectors.append(vec)
        return vectors


def iter_text_files(repo_path: Path) -> Iterable[Path]:
    for path in repo_path.rglob("*"):
        rel = path.relative_to(repo_path)
        if path.is_dir() or any(part in {".git", ".venv", ".codepilot", "storage", "__pycache__"} for part in rel.parts):
            continue
        if path.suffix in TEXT_SUFFIXES and path.stat().st_size <= 200_000:
            yield path


def get_collection(chroma_path: Path, repo_path: Path):
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    name = "repo_" + hashlib.sha1(str(repo_path.resolve()).encode()).hexdigest()[:16]
    return client.get_or_create_collection(name=name, embedding_function=HashEmbedding())


def index_repository(repo_path: Path, chroma_path: Path) -> dict[str, object]:
    collection = get_collection(chroma_path, repo_path)
    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict[str, str]] = []
    for path in iter_text_files(repo_path):
        rel = str(path.relative_to(repo_path))
        text = path.read_text(encoding="utf-8", errors="replace")
        ids.append(hashlib.sha1(rel.encode()).hexdigest())
        docs.append(text[:20_000])
        metas.append({"path": rel})
    if ids:
        collection.upsert(ids=ids, documents=docs, metadatas=metas)
    return {"indexed_files": len(ids), "collection": collection.name}


def search_repository(repo_path: Path, chroma_path: Path, query: str, limit: int = 5) -> list[dict[str, str]]:
    collection = get_collection(chroma_path, repo_path)
    if collection.count() == 0:
        index_repository(repo_path, chroma_path)
    result = collection.query(query_texts=[query], n_results=limit)
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    output: list[dict[str, str]] = []
    for doc, meta in zip(docs, metas):
        output.append({"path": str(meta.get("path", "")), "content": str(doc)[:4000]})
    return output
