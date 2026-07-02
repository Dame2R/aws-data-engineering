"""Configuration loading for the RAG proof of concept.

Required environment variables:
- AWS_REGION
- DB_CLUSTER_ARN
- DB_SECRET_ARN

Optional environment variables:
- DB_NAME, defaults to ragdemo
- EMBED_MODEL_ID, defaults to amazon.titan-embed-text-v2:0
- GEN_MODEL_ID, defaults to eu.amazon.nova-pro-v1:0
- VECTOR_DIM, defaults to 1024

GEN_MODEL_ID must be a Claude or Amazon Nova model ID or inference profile that your
AWS account can access in AWS_REGION. Amazon Nova is an Amazon-owned model and does
not require an AWS Marketplace model subscription, so it avoids the Marketplace
subscribe permissions that third-party models such as Anthropic Claude require.
"""

from __future__ import annotations

from dataclasses import dataclass
import os

DEFAULT_DB_NAME = "ragdemo"
DEFAULT_EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
DEFAULT_GEN_MODEL_ID = "eu.amazon.nova-pro-v1:0"
DEFAULT_VECTOR_DIM = 1024
SUPPORTED_TITAN_V2_DIMS = {256, 512, 1024}


@dataclass(frozen=True)
class Settings:
  """Runtime settings loaded from environment variables."""

  aws_region: str | None
  db_cluster_arn: str | None
  db_secret_arn: str | None
  db_name: str = DEFAULT_DB_NAME
  embed_model_id: str = DEFAULT_EMBED_MODEL_ID
  gen_model_id: str = DEFAULT_GEN_MODEL_ID
  vector_dim: int = DEFAULT_VECTOR_DIM

  def validate(self) -> "Settings":
    """Validate required settings and return self for fluent use."""
    missing = []
    if not self.aws_region:
      missing.append("AWS_REGION")
    if not self.db_cluster_arn:
      missing.append("DB_CLUSTER_ARN")
    if not self.db_secret_arn:
      missing.append("DB_SECRET_ARN")
    if missing:
      raise ValueError("Missing required environment variable(s): " + ", ".join(missing))
    if self.vector_dim not in SUPPORTED_TITAN_V2_DIMS:
      supported = ", ".join(str(dim) for dim in sorted(SUPPORTED_TITAN_V2_DIMS))
      raise ValueError(f"VECTOR_DIM must be one of {supported} for Titan Text Embeddings V2")
    return self


def _read_int(name: str, default: int) -> int:
  raw_value = os.getenv(name)
  if raw_value is None or raw_value.strip() == "":
    return default
  try:
    return int(raw_value)
  except ValueError as exc:
    raise ValueError(f"{name} must be an integer, got {raw_value!r}") from exc


def load_settings(validate: bool = True) -> Settings:
  """Load settings from environment variables."""
  settings = Settings(
      aws_region=os.getenv("AWS_REGION"),
      db_cluster_arn=os.getenv("DB_CLUSTER_ARN"),
      db_secret_arn=os.getenv("DB_SECRET_ARN"),
      db_name=os.getenv("DB_NAME", DEFAULT_DB_NAME),
      embed_model_id=os.getenv("EMBED_MODEL_ID", DEFAULT_EMBED_MODEL_ID),
      gen_model_id=os.getenv("GEN_MODEL_ID", DEFAULT_GEN_MODEL_ID),
      vector_dim=_read_int("VECTOR_DIM", DEFAULT_VECTOR_DIM),
  )
  return settings.validate() if validate else settings
