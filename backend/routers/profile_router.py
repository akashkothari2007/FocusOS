import json
from fastapi import APIRouter, HTTPException
from db import get_conn
from models.profile_models import UpdateProfile

router = APIRouter(prefix="/api/v1")


@router.get("/profile")
def get_profile():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profile WHERE id = 1;")
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Profile not found")
    return row


@router.patch("/profile")
def update_profile(updates: UpdateProfile):
    fields = updates.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # JSONB fields need serialization
    for key in ("projects", "experiences"):
        if key in fields:
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
                raise HTTPException(status_code=404, detail="Profile not found")
    return row
