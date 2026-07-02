"""RAG orchestration for ingestion, retrieval, prompt construction, and answers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.bedrock import BedrockClient
from app.config import Settings, load_settings
from app.db import DataApiClient, vector_to_literal

POC_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = POC_DIR / "data"
DEFAULT_CHUNK_CHARS = 2600
DEFAULT_OVERLAP_CHARS = 350


@dataclass(frozen=True)
class SourceChunk:
  """Retrieved source chunk used for grounded generation."""

  source: str
  chunk_index: int
  content: str
  similarity: float | None = None
  metadata: Any | None = None


def chunk_text(text: str, max_chars: int = DEFAULT_CHUNK_CHARS, overlap_chars: int = DEFAULT_OVERLAP_CHARS) -> list[str]:
  """Split text into overlapping character-based chunks."""
  normalized = "\n".join(line.rstrip() for line in text.strip().splitlines())
  if not normalized:
    return []
  if max_chars <= 0:
    raise ValueError("max_chars must be positive")
  if overlap_chars < 0 or overlap_chars >= max_chars:
    raise ValueError("overlap_chars must be non-negative and smaller than max_chars")

  chunks = []
  start = 0
  text_length = len(normalized)
  while start < text_length:
    end = min(start + max_chars, text_length)
    if end < text_length:
      boundary = normalized.rfind("\n\n", start, end)
      if boundary <= start + max_chars // 2:
        boundary = normalized.rfind(" ", start, end)
      if boundary > start:
        end = boundary
    chunk = normalized[start:end].strip()
    if chunk:
      chunks.append(chunk)
    if end >= text_length:
      break
    start = max(0, end - overlap_chars)
    while start < text_length and normalized[start].isspace():
      start += 1
  return chunks


class RagService:
  """Coordinates Bedrock embeddings, Aurora pgvector retrieval, and generation."""

  def __init__(
      self,
      settings: Settings | None = None,
      db_client: DataApiClient | None = None,
      bedrock_client: BedrockClient | None = None,
  ) -> None:
    self.settings = (settings or load_settings()).validate()
    self.db = db_client or DataApiClient(settings=self.settings)
    self.bedrock = bedrock_client or BedrockClient(settings=self.settings)

  def retrieve(self, question: str, k: int = 5) -> list[SourceChunk]:
    """Retrieve top-k chunks by cosine similarity."""
    if not question.strip():
      raise ValueError("Question must not be empty")
    if k <= 0:
      raise ValueError("k must be positive")

    query_embedding = vector_to_literal(self.bedrock.embed_text(question))
    rows = self.db.execute_statement(
        """
        SELECT
          source,
          chunk_index,
          content,
          metadata,
          1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM documents
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """,
        {"embedding": query_embedding, "limit": k},
    )
    return [
        SourceChunk(
            source=str(row.get("source")),
            chunk_index=int(row.get("chunk_index")),
            content=str(row.get("content")),
            similarity=float(row["similarity"]) if row.get("similarity") is not None else None,
            metadata=row.get("metadata"),
        )
        for row in rows
    ]

  def build_prompt(self, question: str, chunks: list[SourceChunk]) -> tuple[str, str]:
    """Build the prompt and context sent to Claude."""
    context_parts = []
    for index, chunk in enumerate(chunks, start=1):
      context_parts.append(
          f"[{index}] source={chunk.source} chunk={chunk.chunk_index} similarity={chunk.similarity}\n{chunk.content}"
      )
    context = "\n\n".join(context_parts)
    prompt = (
        f"Question: {question}\n\n"
        "Answer using only the context. Include citations for claims using [n]. "
        "After the answer, do not invent extra sources."
    )
    return prompt, context

  def answer(self, question: str, k: int = 5) -> dict[str, Any]:
    """Retrieve context and generate a grounded answer."""
    chunks = self.retrieve(question, k=k)
    prompt, context = self.build_prompt(question, chunks)
    answer_text = self.bedrock.generate(prompt, context)
    return {
        "answer": answer_text,
        "sources": chunks,
    }


def retrieve(question: str, k: int = 5) -> list[SourceChunk]:
  """Retrieve top-k chunks with the default RAG service."""
  return RagService().retrieve(question, k=k)


def build_prompt(question: str, chunks: list[SourceChunk]) -> tuple[str, str]:
  """Build a prompt with the default RAG service settings."""
  settings = load_settings(validate=False)
  return RagService(settings=settings).build_prompt(question, chunks)


def answer(question: str, k: int = 5) -> dict[str, Any]:
  """Answer a question with the default RAG service."""
  return RagService().answer(question, k=k)
