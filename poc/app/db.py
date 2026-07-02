"""Thin RDS Data API wrapper for Aurora PostgreSQL with pgvector.

The RDS Data API does not expose a native pgvector or array parameter type. Vector
values are passed as strings such as "[0.1,0.2]" and cast in SQL with
CAST(:embedding AS vector).
"""

from __future__ import annotations

from decimal import Decimal
import json
import math
from pathlib import Path
import time
from typing import Any, Iterable

import boto3
from botocore.exceptions import ClientError

from app.config import Settings, load_settings

POC_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = POC_DIR / "sql" / "schema.sql"

RESUME_RETRYABLE_ERROR_CODES = frozenset({"DatabaseResumingException"})
RESUME_MAX_ATTEMPTS = 12
RESUME_RETRY_DELAY_SECONDS = 3.0


def vector_to_literal(values: Iterable[float]) -> str:
  """Convert a float iterable to a pgvector text literal."""
  parts = []
  for value in values:
    number = float(value)
    if not math.isfinite(number):
      raise ValueError("Embedding contains a non-finite float")
    parts.append(format(number, ".9g"))
  if not parts:
    raise ValueError("Embedding must contain at least one value")
  return "[" + ",".join(parts) + "]"


def _sql_value(value: Any) -> dict[str, Any]:
  if value is None:
    return {"isNull": True}
  if isinstance(value, bool):
    return {"booleanValue": value}
  if isinstance(value, int) and not isinstance(value, bool):
    return {"longValue": value}
  if isinstance(value, float):
    if not math.isfinite(value):
      raise ValueError("SQL float parameters must be finite")
    return {"doubleValue": value}
  if isinstance(value, Decimal):
    return {"stringValue": str(value)}
  if isinstance(value, (dict, list)):
    return {"stringValue": json.dumps(value, separators=(",", ":"))}
  return {"stringValue": str(value)}


def to_sql_parameter(name: str, value: Any, type_hint: str | None = None) -> dict[str, Any]:
  """Convert a Python value to a Data API SqlParameter."""
  parameter = {"name": name, "value": _sql_value(value)}
  if type_hint:
    parameter["typeHint"] = type_hint
  return parameter


def _field_value(field: dict[str, Any]) -> Any:
  if field.get("isNull"):
    return None
  for key in ("stringValue", "longValue", "doubleValue", "booleanValue", "blobValue"):
    if key in field:
      return field[key]
  if "arrayValue" in field:
    return field["arrayValue"]
  return None


def _parse_records(response: dict[str, Any]) -> list[dict[str, Any]]:
  formatted_records = response.get("formattedRecords")
  if formatted_records:
    parsed = json.loads(formatted_records)
    if isinstance(parsed, list):
      return parsed
    return [parsed]

  records = response.get("records", [])
  metadata = response.get("columnMetadata", [])
  column_names = [column.get("name", f"column_{index}") for index, column in enumerate(metadata)]
  parsed_records = []
  for record in records:
    row = {}
    for index, field in enumerate(record):
      column_name = column_names[index] if index < len(column_names) else f"column_{index}"
      row[column_name] = _field_value(field)
    parsed_records.append(row)
  return parsed_records


def split_sql_statements(sql_text: str) -> list[str]:
  """Split simple SQL scripts into executable statements.

  This parser handles comments and quoted strings used by the PoC schema files.
  It is not intended to be a general PostgreSQL parser.
  """
  statements = []
  current = []
  in_single_quote = False
  in_double_quote = False
  in_line_comment = False
  in_block_comment = False
  index = 0
  while index < len(sql_text):
    char = sql_text[index]
    next_char = sql_text[index + 1] if index + 1 < len(sql_text) else ""

    if in_line_comment:
      current.append(char)
      if char == "\n":
        in_line_comment = False
      index += 1
      continue

    if in_block_comment:
      current.append(char)
      if char == "*" and next_char == "/":
        current.append(next_char)
        in_block_comment = False
        index += 2
      else:
        index += 1
      continue

    if not in_single_quote and not in_double_quote:
      if char == "-" and next_char == "-":
        current.append(char)
        current.append(next_char)
        in_line_comment = True
        index += 2
        continue
      if char == "/" and next_char == "*":
        current.append(char)
        current.append(next_char)
        in_block_comment = True
        index += 2
        continue

    if char == "'" and not in_double_quote:
      current.append(char)
      if in_single_quote and next_char == "'":
        current.append(next_char)
        index += 2
        continue
      in_single_quote = not in_single_quote
      index += 1
      continue

    if char == '"' and not in_single_quote:
      in_double_quote = not in_double_quote
      current.append(char)
      index += 1
      continue

    if char == ";" and not in_single_quote and not in_double_quote:
      statement = "".join(current).strip()
      if statement:
        statements.append(statement)
      current = []
      index += 1
      continue

    current.append(char)
    index += 1

  statement = "".join(current).strip()
  if statement:
    statements.append(statement)
  return statements


class DataApiClient:
  """Small convenience wrapper around boto3 rds-data execute_statement."""

  def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
    self.settings = (settings or load_settings()).validate()
    self.client = client or boto3.client("rds-data", region_name=self.settings.aws_region)

  def execute_statement(
      self,
      sql: str,
      params: dict[str, Any] | list[dict[str, Any]] | None = None,
      type_hints: dict[str, str] | None = None,
      include_result_metadata: bool = True,
      format_records_as: str | None = None,
  ) -> list[dict[str, Any]]:
    """Execute a SQL statement and return rows as dictionaries."""
    request: dict[str, Any] = {
        "resourceArn": self.settings.db_cluster_arn,
        "secretArn": self.settings.db_secret_arn,
        "database": self.settings.db_name,
        "sql": sql,
        "includeResultMetadata": include_result_metadata,
    }
    if params:
      if isinstance(params, dict):
        hints = type_hints or {}
        request["parameters"] = [to_sql_parameter(name, value, hints.get(name)) for name, value in params.items()]
      else:
        request["parameters"] = params
    if format_records_as:
      request["formatRecordsAs"] = format_records_as

    response = self._call_with_resume_retry(request)
    return _parse_records(response)

  def _call_with_resume_retry(self, request: dict[str, Any]) -> dict[str, Any]:
    """Call the Data API, retrying while a scaled-to-zero cluster resumes.

    With a minimum capacity of 0 ACU the Aurora Serverless v2 cluster pauses when
    idle. The first Data API call after an idle period can raise
    DatabaseResumingException while the cluster wakes up. Retry briefly instead of
    failing the ingest or query run.
    """
    for attempt in range(1, RESUME_MAX_ATTEMPTS + 1):
      try:
        return self.client.execute_statement(**request)
      except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "")
        if code not in RESUME_RETRYABLE_ERROR_CODES or attempt == RESUME_MAX_ATTEMPTS:
          raise
        time.sleep(RESUME_RETRY_DELAY_SECONDS)
    raise RuntimeError("Data API call exhausted resume retries without a response")

  def execute_script(self, sql_text: str) -> None:
    """Execute a semicolon-delimited SQL script statement by statement."""
    for statement in split_sql_statements(sql_text):
      self.execute_statement(statement, include_result_metadata=False)

  def ensure_schema(self) -> None:
    """Create pgvector extension, documents table, and HNSW index if needed."""
    sql_text = SCHEMA_PATH.read_text(encoding="utf-8")
    if self.settings.vector_dim != 1024:
      sql_text = sql_text.replace("vector(1024)", f"vector({self.settings.vector_dim})")
    self.execute_script(sql_text)


def ensure_schema(settings: Settings | None = None) -> None:
  """Create schema objects using environment settings."""
  DataApiClient(settings=settings).ensure_schema()
