"""Fetches recent emails from Microsoft Graph."""

import httpx
import logging
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