"""Query the RAG proof of concept from the command line.

With a question argument the script answers once and exits. Without arguments it
starts an interactive chat loop, which is handy for a live demo recording.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

if __package__ is None or __package__ == "":
  sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag import RagService

EXIT_COMMANDS = frozenset({"exit", "quit", ":q"})


def _print_result(result: dict[str, Any]) -> None:
  """Print the answer and cited sources with similarity scores."""
  print("Answer:\n")
  print(result["answer"])
  print("\nSources:")
  for index, chunk in enumerate(result["sources"], start=1):
    similarity = "n/a" if chunk.similarity is None else f"{chunk.similarity:.4f}"
    print(f"[{index}] {chunk.source}#chunk-{chunk.chunk_index} similarity={similarity}")
    print(chunk.content[:500].replace("\n", " "))
    if len(chunk.content) > 500:
      print("...")


def _run_interactive(service: RagService) -> int:
  """Read questions in a loop until the user exits."""
  print("Interactive RAG chat. Ask a question and press Enter.")
  print('Type "exit" or "quit" (or press Ctrl-D) to leave.\n')
  while True:
    try:
      question = input("You> ").strip()
    except (EOFError, KeyboardInterrupt):
      print()
      return 0
    if not question:
      continue
    if question.lower() in EXIT_COMMANDS:
      return 0
    try:
      result = service.answer(question)
    except Exception as error:  # keep the demo loop alive on transient errors
      print(f"Error: {error}\n")
      continue
    _print_result(result)
    print()


def main(argv: list[str] | None = None) -> int:
  """Answer a single question from args, or start an interactive chat loop."""
  args = list(sys.argv[1:] if argv is None else argv)
  service = RagService()

  question = " ".join(args).strip()
  if not question:
    return _run_interactive(service)

  _print_result(service.answer(question))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
