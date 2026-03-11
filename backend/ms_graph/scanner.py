"""Fetches recent emails from Microsoft Graph."""

import httpx
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from ms_graph.graph_client import refresh_access_token

log = logging.getLogger("scanner")


async def fetch_recent_emails(n: int = 20) -> list:
    log.info(f"Fetching last {n} emails")

    access_token = await refresh_access_token()

    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://graph.microsoft.com/v1.0/me/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "$top": n,
                "$orderby": "receivedDateTime desc",
                "$select": "id,subject,from,receivedDateTime,bodyPreview",
            },
        )
        if r.status_code != 200:
            log.error(f"Failed to fetch emails: {r.status_code} {r.text}")
        r.raise_for_status()

        emails = r.json()["value"]
        log.info(f"Fetched {len(emails)} emails")
        return emails


async def fetch_todays_and_yesterdays_emails() -> list:
    """Fetch emails received yesterday and today (Toronto time)."""
    toronto = ZoneInfo("America/Toronto")
    now = datetime.now(toronto)
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    filter_from = yesterday_start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    filter_to = tomorrow_start.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    log.info(f"Fetching emails from {filter_from} to {filter_to}")
    access_token = await refresh_access_token()

    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://graph.microsoft.com/v1.0/me/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "$filter": f"receivedDateTime ge {filter_from} and receivedDateTime lt {filter_to}",
                "$orderby": "receivedDateTime desc",
                "$select": "id,subject,from,receivedDateTime,bodyPreview,webLink",
                "$top": 50,
            },
        )
        r.raise_for_status()
        emails = r.json()["value"]
        log.info(f"Fetched {len(emails)} emails for yesterday+today")
        return emails