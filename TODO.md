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
* Add jobs with ARQ + Redis
* Source adapters (URL, PDF, text, YouTube), youtube-transcript-api (YouTube); IBM Docling
* Audio/podcast transcription (Whisper local)
* SQLModel tables + Pydantic schemas
/