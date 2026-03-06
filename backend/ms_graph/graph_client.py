import urllib.parse
import os
import logging

log = logging.getLogger("graph_client")

def get_auth_url():
    params = {
        "client_id": os.environ["CLIENT_ID"],
        "response_type": "code",
        "redirect_uri": "http://localhost:8000/auth/callback",
        "scope": "Mail.Read offline_access",
        "response_mode": "query"
    }
    tenant_id = os.environ["TENANT_ID"]
    return f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize?" + urllib.parse.urlencode(params)

async def exchange_code_for_tokens(code: str) -> dict:
    import httpx
    log.info("Exchanging auth code for tokens")
    data = {
        "client_id": os.environ["CLIENT_ID"],
        "client_secret": os.environ["CLIENT_SECRET"],
        "code": code,
        "redirect_uri": "http://localhost:8000/auth/callback",
        "grant_type": "authorization_code"
    }
    tenant_id = os.environ["TENANT_ID"]
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            data=data
        )
        if r.status_code != 200:
            log.error(f"Failed to exchange code for tokens: {r.status_code} {r.text}")
        r.raise_for_status()
        return r.json()