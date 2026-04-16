from __future__ import annotations

from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class Embedder:
    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text, convert_to_numpy=True).tolist()
