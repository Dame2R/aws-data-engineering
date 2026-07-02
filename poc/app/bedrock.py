"""Bedrock model calls for embeddings and grounded answer generation."""

from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.config import Config

from app.config import Settings, load_settings


class BedrockClient:
  """Wrapper for Amazon Bedrock Runtime InvokeModel calls."""

  def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
    self.settings = (settings or load_settings()).validate()
    self.client = client or boto3.client(
        "bedrock-runtime",
        region_name=self.settings.aws_region,
        config=Config(read_timeout=3600, retries={"max_attempts": 3, "mode": "standard"}),
    )

  def _invoke_json(self, model_id: str, body: dict[str, Any]) -> dict[str, Any]:
    response = self.client.invoke_model(
        modelId=model_id,
        body=json.dumps(body).encode("utf-8"),
        contentType="application/json",
        accept="application/json",
    )
    payload = response["body"].read()
    return json.loads(payload.decode("utf-8"))

  def embed_text(self, text: str) -> list[float]:
    """Embed text with Titan Text Embeddings V2."""
    body = {
        "inputText": text,
        "dimensions": self.settings.vector_dim,
        "normalize": True,
    }
    result = self._invoke_json(self.settings.embed_model_id, body)
    embedding = result.get("embedding")
    if not isinstance(embedding, list) or not all(isinstance(value, (int, float)) for value in embedding):
      raise ValueError("Bedrock embedding response did not contain a numeric embedding list")
    if len(embedding) != self.settings.vector_dim:
      raise ValueError(f"Expected embedding dimension {self.settings.vector_dim}, got {len(embedding)}")
    return [float(value) for value in embedding]

  def generate(self, prompt: str, context: str = "") -> str:
    """Generate an answer with a Claude Messages API model on Bedrock."""
    system_prompt = (
        "You are a concise AWS RAG assistant. Answer only from the provided context. "
        "If the context does not contain the answer, say that the corpus does not provide enough information. "
        "Cite sources using bracketed source numbers such as [1]."
    )
    user_text = prompt if not context else f"Context:\n{context}\n\nQuestion and instructions:\n{prompt}"
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 800,
        "temperature": 0.2,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_text,
                    }
                ],
            }
        ],
    }
    result = self._invoke_json(self.settings.gen_model_id, body)
    content = result.get("content", [])
    if isinstance(content, list):
      text_blocks = [block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
      answer = "".join(text_blocks).strip()
      if answer:
        return answer
    raise ValueError("Bedrock generation response did not contain text content")


_default_client: BedrockClient | None = None


def _client() -> BedrockClient:
  global _default_client
  if _default_client is None:
    _default_client = BedrockClient()
  return _default_client


def embed_text(text: str) -> list[float]:
  """Embed text with the default Bedrock client."""
  return _client().embed_text(text)


def generate(prompt: str, context: str = "") -> str:
  """Generate text with the default Bedrock client."""
  return _client().generate(prompt, context)
