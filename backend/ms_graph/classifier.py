"""Email classifier — newsletter senders bypass AI; everything else goes through AI for tasks/news."""

import logging
from ai import chat_json
from prompts import email_classifier_messages

log = logging.getLogger("classifier")


def _get_newsletters() -> set:
    """Load newsletter sender addresses from profile. Returns lowercase set."""
    try:
        from db import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT newsletters FROM profile WHERE id = 1")
                row = cur.fetchone()
        newsletters = (row.get("newsletters") or []) if row else []
        return {addr.lower().strip() for addr in newsletters if addr}
    except Exception:
        log.warning("Could not fetch newsletters from profile, defaulting to empty set")
        return set()


async def classify_emails(emails: list[dict]) -> dict:
    """
    Returns {"tasks": [...], "news": [...]}.

    Newsletter senders (from profile): immediately classified as news using subject as title, no AI.
    All others: AI call for is_task / is_news. If AI fails, the email is skipped (newsletters
    are caught before the AI call so they're always safe).
    """
    if not emails:
        return {"tasks": [], "news": []}

    newsletter_senders = _get_newsletters()
    log.info(f"Loaded {len(newsletter_senders)} newsletter sender(s)")

    tasks = []
    news = []

    for email in emails:
        email_id = email.get("id")
        subject = email.get("subject") or "(no subject)"
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "unknown").lower()
        preview = email.get("bodyPreview") or ""

        # Newsletter check — no AI needed
        # Supports full address (e.g. "hi@tldr.tech") or domain (e.g. "tldr.tech")
        sender_domain = sender.split("@")[-1] if "@" in sender else sender
        if sender in newsletter_senders or sender_domain in newsletter_senders:
            log.info(f"Newsletter: {subject[:60]} (from {sender})")
            news.append({"email_id": email_id, "suggested_title": subject})
            continue

        # AI classification for everything else
        try:
            result = chat_json(email_classifier_messages(subject, sender, preview))

            if result.get("is_task"):
                log.info(f"Task: {result.get('suggested_title')}")
                tasks.append({
                    "email_id": email_id,
                    "suggested_title": result.get("suggested_title"),
                    "web_link": email.get("webLink"),
                })
            else:
                log.info(f"Skipped: {subject[:60]}")

        except Exception:
            log.exception(f"AI classification failed for: {subject[:60]}")

    log.info(f"Classified {len(tasks)} tasks, {len(news)} news from {len(emails)} emails")
    return {"tasks": tasks, "news": news}
