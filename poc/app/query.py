"""Query the RAG proof of concept from the command line.

With a question argument the script answers once and exits. Without arguments it
starts an interactive chat loop, which is handy for a live demo recording. Output
uses ANSI colors and separators when writing to a terminal; set NO_COLOR to disable.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any
import warnings

# Keep the demo terminal clean: hide the boto3 Python 3.9 deprecation notice.
warnings.filterwarnings("ignore", message=".*Boto3 will no longer support Python.*")

if __package__ is None or __package__ == "":
  sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.rag import RagService

EXIT_COMMANDS = frozenset({"exit", "quit", ":q"})
SOURCE_PREVIEW_CHARS = 240
WIDTH = 68

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
_CODES = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "magenta": "\033[35m",
}


def _c(text: str, *styles: str) -> str:
  """Wrap text in ANSI styles when color output is enabled."""
  if not _USE_COLOR or not styles:
    return text
  prefix = "".join(_CODES.get(style, "") for style in styles)
  return f"{prefix}{text}{_CODES['reset']}"


def _rule(char: str = "─") -> str:
  return _c(char * WIDTH, "dim")


def _print_result(result: dict[str, Any]) -> None:
  """Print the answer and cited sources with similarity scores."""
  print()
  print(_rule())
  print(_c("ANSWER", "bold", "cyan"))
  print(_rule())
  print(result["answer"].strip())
  print()
  print(_rule())
  print(_c("SOURCES", "bold", "cyan") + _c("  (preview, ranked by cosine similarity)", "dim"))
  print(_rule())
  for index, chunk in enumerate(result["sources"], start=1):
    similarity = "n/a" if chunk.similarity is None else f"{chunk.similarity:.4f}"
    label = _c(f"[{index}]", "bold", "yellow")
    name = _c(str(chunk.source), "bold")
    meta = _c(f"chunk {chunk.chunk_index}", "dim") + _c("  sim ", "dim") + _c(similarity, "green")
    print(f"{label} {name}  {meta}")
    preview = chunk.content[:SOURCE_PREVIEW_CHARS].replace("\n", " ").strip()
    suffix = _c(" ...", "dim") if len(chunk.content) > SOURCE_PREVIEW_CHARS else ""
    print(f"    {_c(preview, 'dim')}{suffix}")
    print()


def _run_interactive(service: RagService) -> int:
  """Read questions in a loop until the user exits."""
  print(_c("=" * WIDTH, "cyan"))
  print(_c("  AWS RAG PoC", "bold", "cyan") + _c("   Aurora pgvector + Amazon Bedrock", "dim"))
  print(_c("=" * WIDTH, "cyan"))
  print(_c('Ask a question and press Enter. Type "exit" or Ctrl-D to leave.', "dim"))
  while True:
    try:
      question = input("\n" + _c("You > ", "bold", "magenta")).strip()
    except (EOFError, KeyboardInterrupt):
      print()
      return 0
    if not question:
      continue
    if question.lower() in EXIT_COMMANDS:
      print(_c("Bye.", "dim"))
      return 0
    try:
      result = service.answer(question)
    except Exception as error:  # keep the demo loop alive on transient errors
      print(_c(f"Error: {error}", "yellow"))
      continue
    _print_result(result)


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
