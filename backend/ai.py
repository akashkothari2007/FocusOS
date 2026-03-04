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


def fmt_profile(profile) -> str:
    """Render profile experiences + projects as plain text for prompt context."""
    if not profile:
        return ""
    lines = []
    for exp in profile.get("experiences") or []:
        role    = exp.get("role", "")
        company = exp.get("company", "")
        date    = exp.get("date", "")
        lines.append(f"Experience: {role} at {company} ({date})")
        for bullet in exp.get("bullets") or []:
            lines.append(f"  - {bullet}")
    for proj in profile.get("projects") or []:
        title = proj.get("title", "")
        desc  = proj.get("description", "")
        tech  = proj.get("tech", "")
        lines.append(f"Project: {title}" + (f" [{tech}]" if tech else ""))
        if desc:
            lines.append(f"  {desc}")
    return "\n".join(lines)
