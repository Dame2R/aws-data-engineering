"""Query the RAG proof of concept from the command line."""

from __future__ import annotations

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
  sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag import RagService


def _usage() -> str:
  return 'Usage: python poc/app/query.py "some question"'


def main(argv: list[str] | None = None) -> int:
  """Embed the question, retrieve context, generate an answer, and print sources."""
  args = list(sys.argv[1:] if argv is None else argv)
  if not args:
    print(_usage())
    return 2

  question = " ".join(args).strip()
  if not question:
    print(_usage())
    return 2

  result = RagService().answer(question)
  print("Answer:\n")
  print(result["answer"])
  print("\nSources:")
  for index, chunk in enumerate(result["sources"], start=1):
    similarity = "n/a" if chunk.similarity is None else f"{chunk.similarity:.4f}"
    print(f"[{index}] {chunk.source}#chunk-{chunk.chunk_index} similarity={similarity}")
    print(chunk.content[:500].replace("\n", " "))
    if len(chunk.content) > 500:
      print("...")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
