"""Email classifier — decides if an email should become a todo or a news item."""

import logging
from ai import chat_json
from prompts import email_classifier_messages

log = logging.getLogger("classifier")


async def classify_emails(emails: list[dict]) -> dict:
    """
    Takes a list of emails from the scanner.
    Returns {"tasks": [...], "news": [...]}
    Tasks get their own todo; news get their body stored in scanned_email_ids.
    """
    if not emails:
        return {"tasks": [], "news": []}

    tasks = []
    news = []

    for email in emails:
        subject = email.get("subject") or "(no subject)"
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "unknown")
        preview = email.get("bodyPreview") or ""

        try:
            result = chat_json(email_classifier_messages(subject, sender, preview))

            if result.get("is_task"):
                log.info(f"Task: {result.get('suggested_title')}")
                tasks.append({
                    "email_id": email.get("id"),
                    "suggested_title": result.get("suggested_title"),
                    "web_link": email.get("webLink"),
                })
            elif result.get("is_news"):
                log.info(f"News: {result.get('suggested_title')}")
                news.append({
                    "email_id": email.get("id"),
                    "suggested_title": result.get("suggested_title"),
                })
            else:
                log.info(f"Skipped: {subject[:60]}")

        except Exception:
            log.exception(f"Failed to classify email: {subject[:60]}")

    log.info(f"Classified {len(tasks)} tasks, {len(news)} news from {len(emails)} emails")
    return {"tasks": tasks, "news": news}
