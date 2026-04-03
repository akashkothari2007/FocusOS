import json
from fastapi import APIRouter, HTTPException
from db import get_conn
from models.routine_models import CreateRoutine, UpdateRoutine, ReorderRoutines

router = APIRouter(prefix="/api/v1")


@router.get("/routines")
def get_routines():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM routines ORDER BY sort_order ASC, id ASC;")
            rows = cur.fetchall()
    return {"routines": rows}


@router.post("/routines", status_code=201)
def create_routine(routine: CreateRoutine):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO routines (name, items) VALUES (%s, %s) RETURNING *;",
                (routine.name, json.dumps(routine.items))
            )
            row = cur.fetchone()
    return row


@router.patch("/routines/{routine_id}")
def update_routine(routine_id: int, updates: UpdateRoutine):
    fields = {}
    if updates.name is not None:
        fields["name"] = updates.name
    if updates.items is not None:
        fields["items"] = json.dumps(updates.items)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [routine_id]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE routines SET {set_clause} WHERE id = %s RETURNING *;",
                values
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Routine not found")
    return row


@router.post("/routines/reorder")
def reorder_routines(body: ReorderRoutines):
    ids = body.ids
    orders = [i * 10 for i in range(len(ids))]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE routines SET sort_order = v.ord
                FROM (SELECT unnest(%s::int[]) AS id, unnest(%s::int[]) AS ord) AS v
                WHERE routines.id = v.id;
                """,
                (ids, orders)
            )
        conn.commit()
    return {"ok": True}


@router.delete("/routines/{routine_id}", status_code=204)
def delete_routine(routine_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM routines WHERE id = %s RETURNING id;", (routine_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Routine not found")
    return
