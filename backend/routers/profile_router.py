import json
import logging
from fastapi import APIRouter, HTTPException
from db import get_conn
from models.profile_models import UpdateProfile

log = logging.getLogger("profile_router")
router = APIRouter(prefix="/api/v1")


@router.get("/profile")
def get_profile():
    log.info("GET /profile")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profile WHERE id = 1;")
            row = cur.fetchone()
            if not row:
                log.warning("GET /profile — not found")
                raise HTTPException(status_code=404, detail="Profile not found")
    experiences_count = len(row.get("experiences") or [])
    projects_count = len(row.get("projects") or [])
    log.info(f"GET /profile OK | experiences={experiences_count} | projects={projects_count}")
    return row


@router.patch("/profile")
def update_profile(updates: UpdateProfile):
    fields = updates.model_dump(exclude_none=True)
    log.info(f"PATCH /profile | fields={list(fields.keys())}")
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # JSONB fields need serialization
    for key in ("projects", "experiences", "newsletters"):
        if key in fields:
            log.debug(f"PATCH /profile: serializing JSONB field '{key}' ({len(fields[key])} items)")
            fields[key] = json.dumps(fields[key])

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values())

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE profile SET {set_clause} WHERE id = 1 RETURNING *;",
                values
            )
            row = cur.fetchone()
            if not row:
                log.warning("PATCH /profile — not found")
                raise HTTPException(status_code=404, detail="Profile not found")
    log.info("PATCH /profile OK")
    return row
