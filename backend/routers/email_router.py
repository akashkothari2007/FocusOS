from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from db import get_conn
from ms_graph.graph_client import get_auth_url, exchange_code_for_tokens
from datetime import datetime, timezone, timedelta
from typing import Optional
from ms_graph.scanner import fetch_recent_emails
from ms_graph.classifier import classify_emails
import logging
from scheduler import run_email_scan
log = logging.getLogger("email_router")
router = APIRouter()

ERROR_REDIRECT = "http://localhost:5173/profile?auth_error=true"

@router.get("/auth/login")
def login():
    return RedirectResponse(url=get_auth_url())

@router.get("/auth/callback")
async def callback(code: Optional[str] = None, error: Optional[str] = None):
    if error:
        log.error(f"OAuth error from Microsoft: {error}")
        return RedirectResponse(url=ERROR_REDIRECT)
    try:
        log.info(f"Callback received with code: {code}")
        tokens = await exchange_code_for_tokens(code)
        log.info("Tokens received successfully")
        access_token = tokens["access_token"]
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM email_accounts")
                cur.execute("""
                    INSERT INTO email_accounts (email, access_token, refresh_token, expires_at)
                    VALUES (%s, %s, %s, %s)
                """, ("akash@kotharigroup.com", access_token, refresh_token, expires_at))
    except Exception as exc:
        log.error(f"Failed to complete OAuth flow: {exc}")
        return RedirectResponse(url=ERROR_REDIRECT)

    return RedirectResponse(url="http://localhost:5173/profile")

@router.get("/auth/status")
def status():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT email, expires_at FROM email_accounts
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cur.fetchone()
    if not row:
        return {"connected": False}
    return {
        "connected": True,
        "email": row["email"],
        "expires_at": row["expires_at"]
    }

from ms_graph.graph_client import refresh_access_token

@router.post("/auth/refresh")
async def manual_refresh():
    token = await refresh_access_token()
    return {"message": "Token refreshed", "expires_soon": False}
