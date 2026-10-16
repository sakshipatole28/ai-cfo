# ADR-0002: Postgres as the platform; no Celery/Redis; no separate vector database

- **Status:** Accepted, 2026-10-16
- **Context:** v2 used Celery + Redis, which isn't free to host. A separate vector database (Chroma, Qdrant, Pinecone) adds another service to secure, sync, keep India-resident and isolate per tenant. The RAG corpus is thousands of chunks, not millions.
- **Decision:**
  - One Postgres (17 + pgvector) provides relational data, vectors (HNSW), full-text search, the job queue (Procrastinate) and periodic tasks.
  - Hosted on Supabase (Mumbai) or self-hosted on an India-region VM; Docker Compose for development.
  - Every component sits behind an interface (`JobQueue`, `VectorStore`) so it can be swapped.
- **Consequences:**
  - One backup, one residency story, one RLS model.
  - Procrastinate's maintainer bus factor is a known risk; the fallbacks are DBOS and Hatchet.
  - Qdrant is used only as a research-benchmark baseline.
  - Supabase free projects pause after 7 days idle and have no automatic backups, so a nightly encrypted `pg_dump` job is required.
