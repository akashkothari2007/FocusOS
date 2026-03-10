"""Email classifier — decides if an email should become a todo."""

import logging
import json
from ai import chat_json
from prompts import email_classifier_messages

log = logging.getLogger("classifier")


async def classify_emails(emails: list[dict]) -> list[dict]:
    """
    Takes a list of emails from the scanner.
    Returns only the ones that should become todos, with suggested title + priority.
    """
    if not emails:
        return []

    tasks = []
    for email in emails:
        subject = email.get("subject", "(no subject)")
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "unknown")
        preview = email.get("bodyPreview", "")

        messages = email_classifier_messages(subject, sender, preview)
        result = chat_json(messages)

        if result.get("is_task"):
            log.info(f"Task found: [{result.get('priority')}] {result.get('suggested_title')}")
            tasks.append({
                "email_id": email.get("id"),
                "subject": subject,
                "sender": sender,
                "suggested_title": result.get("suggested_title"),
                "priority": result.get("priority", "medium"),
                "reason": result.get("reason"),
            })
        else:
            log.info(f"Skipped: {subject[:50]} — {result.get('reason')}")

    log.info(f"Classified {len(tasks)} tasks from {len(emails)} emails")
    return tasks