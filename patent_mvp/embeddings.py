from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from patent_mvp.text_utils import sha256_hex

EXPECTED_EMBED_DIM = 768


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str, cache_dir: str = "embeddings_cache") -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = model_name
        self.model = SentenceTransformer(model_name, device=device)
        self.cache_path = Path(cache_dir) / "embeddings.json"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}

    def _validate_dimension(self, dim: int) -> None:
        if dim != EXPECTED_EMBED_DIM:
            raise ValueError(
                f"Embedding dimension mismatch: model '{self.model_name}' returned {dim} dims, "
                f"but database schema expects {EXPECTED_EMBED_DIM} dims (vector({EXPECTED_EMBED_DIM})). "
                "Set EMBEDDING_MODEL to a 768-d model or run a DB migration to change vector dimension."
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        missing: list[str] = []
        missing_idx: list[int] = []
        for i, text in enumerate(texts):
            key = sha256_hex(text)
            if key in self.cache:
                cached_vec = self.cache[key]
                self._validate_dimension(len(cached_vec))
                results.append(cached_vec)
            else:
                results.append([])
                missing.append(text)
                missing_idx.append(i)

        if missing:
            new_vecs = self.model.encode(missing, convert_to_numpy=True, normalize_embeddings=True)
            if len(new_vecs) > 0:
                self._validate_dimension(int(new_vecs.shape[1]))
            for i, vec in enumerate(new_vecs):
                key = sha256_hex(missing[i])
                vector = vec.tolist()
                self.cache[key] = vector
                results[missing_idx[i]] = vector
            self.cache_path.write_text(json.dumps(self.cache))
        return results
