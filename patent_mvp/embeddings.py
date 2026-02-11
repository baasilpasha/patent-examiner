from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str, cache_path: Path, batch_size: int = 64) -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading embedding model %s on %s", model_name, device)
        self.model = SentenceTransformer(model_name, device=device)
        self.batch_size = batch_size
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        if self.cache_path.exists():
            self.cache = json.loads(self.cache_path.read_text())
        else:
            self.cache = {}

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def embed(self, texts: list[str]) -> list[list[float]]:
        result: list[list[float] | None] = [None] * len(texts)
        misses: list[tuple[int, str, str]] = []
        for idx, txt in enumerate(texts):
            h = self._hash(txt)
            if h in self.cache:
                result[idx] = self.cache[h]
            else:
                misses.append((idx, h, txt))

        if misses:
            vectors = self.model.encode([m[2] for m in misses], batch_size=self.batch_size, normalize_embeddings=True)
            for (idx, h, _), vec in zip(misses, vectors):
                v = vec.tolist()
                self.cache[h] = v
                result[idx] = v
            self.cache_path.write_text(json.dumps(self.cache))

        return [r for r in result if r is not None]
