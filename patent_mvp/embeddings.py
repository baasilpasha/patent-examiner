from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from patent_mvp.text_utils import sha256_hex


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str, cache_dir: str = "embeddings_cache") -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(model_name, device=device)
        self.cache_path = Path(cache_dir) / "embeddings.json"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache = json.loads(self.cache_path.read_text()) if self.cache_path.exists() else {}

    def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        missing: list[str] = []
        missing_idx: list[int] = []
        for i, text in enumerate(texts):
            key = sha256_hex(text)
            if key in self.cache:
                results.append(self.cache[key])
            else:
                results.append([])
                missing.append(text)
                missing_idx.append(i)

        if missing:
            new_vecs = self.model.encode(missing, convert_to_numpy=True, normalize_embeddings=True)
            for i, vec in enumerate(new_vecs):
                key = sha256_hex(missing[i])
                vector = vec.tolist()
                self.cache[key] = vector
                results[missing_idx[i]] = vector
            self.cache_path.write_text(json.dumps(self.cache))
        return results
