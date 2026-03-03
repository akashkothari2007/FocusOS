"""Azure OpenAI client and helpers."""

import json
import os
from urllib.parse import urlparse, parse_qs

from openai import AzureOpenAI

MODEL = "gpt-4o"

_az_client = None


def get_az() -> AzureOpenAI:
    global _az_client
    if _az_client is None:
        full_url = os.environ["AZURE_FOUNDRY_ENDPOINT"]
        parsed = urlparse(full_url)
        base_endpoint = f"{parsed.scheme}://{parsed.netloc}"
        api_version = parse_qs(parsed.query).get("api-version", ["2025-01-01-preview"])[0]
        _az_client = AzureOpenAI(
            azure_endpoint=base_endpoint,
            api_key=os.environ["AZURE_FOUNDRY_API_KEY"],
            api_version=api_version,
        )
    return _az_client


def chat_json(messages: list[dict], retries: int = 2) -> dict:
    """Call the model with json_object response format; retry on failure."""
    exc = None
    for _ in range(retries + 1):
        try:
            resp = get_az().chat.completions.create(
                model=MODEL,
                response_format={"type": "json_object"},
                messages=messages,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
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
