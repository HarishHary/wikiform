from __future__ import annotations

import logging

logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"

# BGE retrieval models expect this prefix on short search queries (not on documents).
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        # Imported lazily: sentence-transformers pulls in torch and is slow to import.
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        return int(self._model.get_embedding_dimension())

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text, convert_to_numpy=True).tolist()

    def embed_many(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        return self._model.encode(texts, batch_size=batch_size, convert_to_numpy=True).tolist()

    def embed_query(self, query: str) -> list[float]:
        """Embed a search query (adds the BGE instruction prefix for BGE models)."""
        if "bge" in self.model_name.lower():
            query = _BGE_QUERY_PREFIX + query
        return self.embed(query)
