import json
import logging
from fastapi import APIRouter, HTTPException
from typing import Optional, Literal
from db import get_conn
from models.todo_models import CreateTodo, UpdateTodo, Link, ReorderTodos, QuickTodo

log = logging.getLogger("todo_router")

router = APIRouter(prefix="/api/v1")


# get all todos either all or by status filtered
@router.get("/todos")
def get_todos(status: Optional[Literal["pending", "done", "on_hold"]] = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status == "pending":
                cur.execute(
                    "SELECT * FROM todos WHERE status IN ('pending', 'on_hold') ORDER BY (due_date IS NULL) ASC, due_date ASC, (status = 'on_hold') ASC, sort_order ASC;"
                )
            elif status:
                cur.execute(
                    "SELECT * FROM todos WHERE status = %s ORDER BY (due_date IS NULL) ASC, due_date ASC, sort_order ASC;",
                    (status,)
                )
            else:
                cur.execute("SELECT * FROM todos ORDER BY (due_date IS NULL) ASC, due_date ASC, sort_order ASC;")
            rows = cur.fetchall()
    return {"todos": rows}


# create a new todo
@router.post("/todos", status_code=201)
def create_todo(todo: CreateTodo):
    subtasks_json = json.dumps([s.model_dump() for s in todo.subtasks])
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(sort_order), 0) + 10 AS next_order FROM todos WHERE status = 'pending' AND due_date IS NULL")
            next_order = cur.fetchone()["next_order"]
            cur.execute(
                """
                INSERT INTO todos (title, description, subtasks, due_date, sort_order)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (todo.title, todo.description, subtasks_json, todo.due_date, next_order)
            )
            row = cur.fetchone()
    return row


# reorder undated todos
@router.post("/todos/reorder")
def reorder_todos(body: ReorderTodos):
    ids = body.ids
    orders = [i * 10 for i in range(len(ids))]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE todos SET sort_order = v.ord
                FROM (SELECT unnest(%s::int[]) AS id, unnest(%s::int[]) AS ord) AS v
                WHERE todos.id = v.id
                """,
                (ids, orders)
            )
    return {"ok": True}


# update a todo
@router.patch("/todos/{todo_id}")
def update_todo(todo_id: int, updates: UpdateTodo):
    fields = updates.model_dump(exclude_none=True)  # drops any field that is None (SO ONLY UPDATES CHANGED FIELDS!!! very cool)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # subtasks and links need JSON serialization if present
    if "subtasks" in fields:
        fields["subtasks"] = json.dumps([s.model_dump() for s in updates.subtasks])
    if "links" in fields:
        fields["links"] = json.dumps([l.model_dump() for l in updates.links])

    set_clause = ", ".join(f"{k} = %s" for k in fields)  # e.g. "title = %s, status = %s"
    values = list(fields.values()) + [todo_id]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE todos SET {set_clause} WHERE id = %s RETURNING *;",
                values
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Todo not found")
    return row


# delete a todo in case of error
@router.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM todos WHERE id = %s RETURNING id;", (todo_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Todo not found")
    return  # 204 = no content


@router.patch("/todos/{todo_id}/hold")
def hold_todo(todo_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE todos SET status = 'on_hold' WHERE id = %s RETURNING *;",
                (todo_id,)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Todo not found")
    return row


@router.patch("/todos/{todo_id}/unhold")
def unhold_todo(todo_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(sort_order) AS max_order FROM todos WHERE status = 'pending' AND due_date IS NULL")
            max_order = cur.fetchone()["max_order"] or 0
            cur.execute(
                "UPDATE todos SET status = 'pending', sort_order = %s WHERE id = %s RETURNING *;",
                (max_order + 10, todo_id)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Todo not found")
    return row


@router.post("/todos/quick-subtask")
def quick_subtask(body: QuickTodo):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, subtasks FROM todos WHERE title ILIKE %s LIMIT 1",
                (f"%{body.project}%",)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Todo not found")
            subtasks = row["subtasks"] or []
            next_id = max((int(s.get("id", 0)) for s in subtasks), default=0) + 1
            subtasks.append({"id": next_id, "title": body.title, "status": "pending", "order": len(subtasks)})
            cur.execute(
                "UPDATE todos SET subtasks = %s WHERE id = %s",
                (json.dumps(subtasks), row["id"])
            )
    return {"message": "Subtask added"}
