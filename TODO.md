* Add in the SKILLS.md
* Need to support for file types:

| Type              | Extensions                                                            |
| ----------------- | --------------------------------------------------------------------- |
| Plain text / code | `.txt .md .py .sql .js .ts .csv .json .yaml .html .xml .bat .ps1 .sh` |
| Word              | `.docx .dotx`                                                         |
| Excel             | `.xlsx .xltx`                                                         |
| PDF               | `.pdf`                                                                |
| PowerPoint        | `.pptx`                                                               |
| Binary            | Noted with size metadata, no text extraction                          |

* Incremental updates & caching
  * **Extraction state**: `_wiki_state.json` tracks file hashes. Unchanged files are skipped on `--incremental` runs (default).
  * **LLM cache**: `_wiki_llm_cache.json` caches LLM responses by content hash. Changing the model invalidates the cache per file. A full rebuild (`--full`) still won't re-call the API for files whose content hasn't changed.
  * Both files are gitignored - they're machine-local caches.

* Add jobs with ARQ + Redis
* Source adapters (URL, PDF, text, YouTube), trafilatura (URLs), youtube-transcript-api (YouTube), pymupdf (fitz) — default; IBM Docling — opt-in via parse-advanced or https://github.com/opendataloader-project/opendataloader-pdf
* Audio/podcast transcription (Whisper local)
* SQLModel tables + Pydantic schemas
* Semantic search (ChromaDB + embeddings), Embedder (sentence-transformers)