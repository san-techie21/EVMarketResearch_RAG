# knowledge_base/

Drop your own documents here, then run:

```
python pipeline/ingest_docs.py
```

(or inside Docker: `docker compose -f infra/docker-compose.yml exec api python pipeline/ingest_docs.py`)

**Supported:** `.txt`, `.md`, `.pdf`

**Grouping (optional):** put files in a sub-folder to tag them with an app/topic
name. A file at `knowledge_base/acme/manual.pdf` is tagged `app_name = acme`.
Files placed directly in this folder are tagged `general`.

After ingestion, the chat answers questions from these documents (with citations),
alongside the EV/energy data. Re-running is safe - duplicates are skipped.
