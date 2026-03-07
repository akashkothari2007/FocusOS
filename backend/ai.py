"""Azure OpenAI client and helpers."""

import json
import logging
import os
import time
from urllib.parse import urlparse, parse_qs

from openai import AzureOpenAI

log = logging.getLogger("ai")

MODEL = "gpt-4o"

_az_client = None


def get_az() -> AzureOpenAI:
    global _az_client
    if _az_client is None:
        log.info("Initializing AzureOpenAI client")
        full_url = os.environ["AZURE_FOUNDRY_ENDPOINT"]
        parsed = urlparse(full_url)
        base_endpoint = f"{parsed.scheme}://{parsed.netloc}"
        api_version = parse_qs(parsed.query).get("api-version", ["2025-01-01-preview"])[0]
        log.info(f"Azure endpoint={base_endpoint} api_version={api_version} model={MODEL}")
        _az_client = AzureOpenAI(
            azure_endpoint=base_endpoint,
            api_key=os.environ["AZURE_FOUNDRY_API_KEY"],
            api_version=api_version,
        )
        log.info("AzureOpenAI client ready")
    return _az_client


def chat_json(messages: list[dict], retries: int = 2) -> dict:
    """Call the model with json_object response format; retry on failure."""
    exc = None
    for attempt in range(retries + 1):
        try:
            t0 = time.time()
            resp = get_az().chat.completions.create(
                model=MODEL,
                response_format={"type": "json_object"},
                messages=messages,
            )
            elapsed = time.time() - t0
            raw = resp.choices[0].message.content
            log.info(f"  AI responded in {elapsed:.1f}s  ({resp.usage.total_tokens} tokens)")
            return json.loads(raw)
        except Exception as e:
            log.error(f"  AI attempt {attempt + 1}/{retries + 1} failed: {type(e).__name__}: {e}")
            exc = e
    raise exc
    
import httpx

def chat_ollama(prompt: str, model: str = "llama3.1:8b") -> str:
    """Call local Ollama instance, returns raw text response."""
    t0 = time.time()
    try:
        r = httpx.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=120.0
        )
        r.raise_for_status()
        elapsed = time.time() - t0
        result = r.json()["response"]
        log.info(f"  Ollama responded in {elapsed:.1f}s")
        return result
    except Exception as e:
        log.error(f"  Ollama failed: {type(e).__name__}: {e}")
        raise



