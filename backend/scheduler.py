# scheduler.py
import json
import logging
from db import get_conn
from ms_graph.scanner import fetch_todays_and_yesterdays_emails
from ms_graph.classifier import classify_emails

log = logging.getLogger("scheduler")


async def run_email_scan():
    log.info("=== Email scan starting ===")
    try:
        # Prune stale entries older than 3 days
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM scanned_email_ids WHERE scanned_at < NOW() - INTERVAL '3 days'")
            conn.commit()

        emails = await fetch_todays_and_yesterdays_emails()
        if not emails:
            log.info("No emails found")
            return

        # Filter out already-scanned email IDs
        email_ids = [e["id"] for e in emails]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT email_id FROM scanned_email_ids WHERE email_id = ANY(%s)",
                    (email_ids,),
                )
                already_scanned = {row["email_id"] for row in cur.fetchall()}

        new_emails = [e for e in emails if e["id"] not in already_scanned]
        log.info(f"{len(new_emails)} new / {len(already_scanned)} already scanned")

        if not new_emails:
            log.info("=== Nothing new to process ===")
            return

        tasks = await classify_emails(new_emails)

        with get_conn() as conn:
            with conn.cursor() as cur:
                for task in tasks:
                    links = json.dumps([{"id": 1, "url": task["web_link"], "label": "View email"}]) if task.get("web_link") else "[]"
                    cur.execute(
                        "INSERT INTO todos (title, status, links) VALUES (%s, 'pending', %s) RETURNING id",
                        (task["suggested_title"], links),
                    )
                    todo_id = cur.fetchone()["id"]
                    log.info(f"  Created todo #{todo_id}: {task['suggested_title']}")

                # Record all new emails as scanned (not just task ones — avoids re-classifying skipped)
                cur.executemany(
                    "INSERT INTO scanned_email_ids (email_id) VALUES (%s) ON CONFLICT DO NOTHING",
                    [(e["id"],) for e in new_emails],
                )
            conn.commit()

        log.info(f"=== Scan done: {len(tasks)} todos from {len(new_emails)} new emails ===")

    except Exception:
        log.exception("Email scan failed")
