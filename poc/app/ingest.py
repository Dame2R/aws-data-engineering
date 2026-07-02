"""Ingest Markdown files into Aurora PostgreSQL pgvector via the RDS Data API."""

from __future__ import annotations

import json
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
  sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.bedrock import BedrockClient
from app.config import load_settings
from app.db import DataApiClient, vector_to_literal
from app.rag import DATA_DIR, chunk_text


def _topic_from_path(path: Path) -> str:
  return path.stem.replace("-", " ")


def ingest_file(path: Path, db: DataApiClient, bedrock: BedrockClient) -> int:
  """Chunk, embed, and upsert a single Markdown file."""
  text = path.read_text(encoding="utf-8")
  chunks = chunk_text(text)
  for index, chunk in enumerate(chunks):
    embedding = vector_to_literal(bedrock.embed_text(chunk))
    metadata = json.dumps({"topic": path.stem, "format": "markdown"}, separators=(",", ":"))
    db.execute_statement(
        """
        INSERT INTO documents (source, chunk_index, content, embedding, metadata)
        VALUES (:source, :chunk_index, :content, CAST(:embedding AS vector), CAST(:metadata AS jsonb))
        ON CONFLICT (source, chunk_index)
        DO UPDATE SET
          content = EXCLUDED.content,
          embedding = EXCLUDED.embedding,
          metadata = EXCLUDED.metadata
        RETURNING id
        """,
        {
            "source": path.name,
            "chunk_index": index,
            "content": chunk,
            "embedding": embedding,
            "metadata": metadata,
        },
    )
  print(f"Ingested {len(chunks)} chunk(s) from {path.name} ({_topic_from_path(path)})")
  return len(chunks)


def main() -> int:
  """Ensure schema and ingest all Markdown files under poc/data."""
  settings = load_settings()
  db = DataApiClient(settings=settings)
  bedrock = BedrockClient(settings=settings)

  print("Ensuring Aurora pgvector schema")
  db.ensure_schema()

  files = sorted(DATA_DIR.glob("*.md"))
  if not files:
    print(f"No Markdown files found in {DATA_DIR}")
    return 1

  total_chunks = 0
  for path in files:
    total_chunks += ingest_file(path, db, bedrock)
  print(f"Complete. {len(files)} file(s), {total_chunks} chunk(s) upserted.")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
