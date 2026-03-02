from fastapi import APIRouter, HTTPException
from db import get_conn
from models.doc_models import CreateDoc, UpdateDoc

router = APIRouter(prefix="/api/v1")


@router.get("/docs")
def get_docs():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM docs ORDER BY created_at DESC;")
            rows = cur.fetchall()
    return {"docs": rows}


@router.post("/docs", status_code=201)
def create_doc(doc: CreateDoc):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO docs (title, content, is_primary)
                VALUES (%s, %s, %s)
                RETURNING *;
                """,
                (doc.title, doc.content, doc.is_primary)
            )
            row = cur.fetchone()
    return row


@router.patch("/docs/{doc_id}")
def update_doc(doc_id: int, updates: UpdateDoc):
    fields = updates.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [doc_id]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE docs SET {set_clause} WHERE id = %s RETURNING *;",
                values
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Doc not found")
    return row


@router.patch("/docs/{doc_id}/set-primary")
def set_primary_doc(doc_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM docs WHERE id = %s;", (doc_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Doc not found")

            cur.execute("UPDATE docs SET is_primary = FALSE WHERE is_primary = TRUE;")
            cur.execute(
                "UPDATE docs SET is_primary = TRUE WHERE id = %s RETURNING *;",
                (doc_id,)
            )
            row = cur.fetchone()
    return row


@router.delete("/docs/{doc_id}", status_code=204)
def delete_doc(doc_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM docs WHERE id = %s RETURNING id;", (doc_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Doc not found")
    return
