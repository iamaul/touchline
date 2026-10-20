"""LLM provider adapter (optional).

Zero-dependency chat-completions client compatible with:
  - Azure AI Foundry "Model-Inference" chat completions endpoint
  - GitHub Models inference endpoint
  - any OpenAI-compatible /chat/completions server

Config via environment (first match wins):
  TOUCHLINE_LLM_BASE_URL + TOUCHLINE_LLM_API_KEY (+ optional TOUCHLINE_LLM_MODEL)
  fallback: GITHUB_TOKEN  ->  https://models.inference.ai.azure.com/chat/completions

If nothing is configured, agents run on deterministic templates (see
narrator/personalizer). Every LLM call is best-effort: a failed call returns
None and the pipeline degrades instead of crashing.

Grounding rule: LLM output is used for phrasing/translation only. Facts
inside packets are substituted by code from MatchState and never handed
to the model for generation.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

GITHUB_MODELS_URL = "https://models.inference.ai.azure.com/chat/completions"
GITHUB_MODELS_DEFAULT_MODEL = "gpt-4o-mini"
REQUEST_TIMEOUT_S = 8.0


@dataclass
class ChatConfig:
    base_url: str
    api_key: str
    model: str
    timeout: float = REQUEST_TIMEOUT_S
    extra: dict = field(default_factory=dict)


def detect_config(env: Optional[dict] = None) -> Optional[ChatConfig]:
    env = env if env is not None else os.environ
    base = env.get("TOUCHLINE_LLM_BASE_URL")
    key = env.get("TOUCHLINE_LLM_API_KEY")
    model = env.get("TOUCHLINE_LLM_MODEL")

    if base and key:
        return ChatConfig(
            base_url=base.rstrip("/"),
            api_key=key,
            model=model or DEFAULT_MODEL_HINT,
        )
    token = env.get("GITHUB_TOKEN")
    if token:
        return ChatConfig(
            base_url=GITHUB_MODELS_URL,
            api_key=token,
            model=model or GITHUB_MODELS_DEFAULT_MODEL,
        )
    return None


DEFAULT_MODEL_HINT = "gpt-4.1-mini"


def chat(cfg: ChatConfig, messages: list, temperature: float = 0.6, max_tokens: int = 350) -> Optional[str]:
    """POST a chat completion; returns first choice content on OK, None on any failure."""
    payload = dict(
        model=cfg.model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        cfg.base_url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg.api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception:
        return None
