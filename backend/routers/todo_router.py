import json
from fastapi import APIRouter, HTTPException
from typing import Optional, Literal
from db import get_conn
from models.todo_models import CreateTodo, UpdateTodo, Link

router = APIRouter(prefix="/api/v1")


# get all todos either all or by status filtered
@router.get("/todos")
def get_todos(status: Optional[Literal["pending", "done"]] = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT * FROM todos WHERE status = %s ORDER BY due_date ASC NULLS LAST;",
                    (status,)
                )
            else:
                cur.execute("SELECT * FROM todos ORDER BY due_date ASC NULLS LAST;")
            rows = cur.fetchall()
    return {"todos": rows}


# create a new todo
@router.post("/todos", status_code=201)
def create_todo(todo: CreateTodo):
    subtasks_json = json.dumps([s.model_dump() for s in todo.subtasks])  # serialize list → JSON string so can be stored in database
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO todos (title, description, subtasks, due_date)
                VALUES (%s, %s, %s, %s)
                RETURNING *;
                """,
                (todo.title, todo.description, subtasks_json, todo.due_date)
            )
            row = cur.fetchone()
    return row


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

@router.post("/todos/quick-subtask")
def quick_subtask(title: str, project: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, subtasks FROM todos WHERE title ILIKE %s LIMIT 1",
                (f"%{project}%",)
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Todo not found")
            subtasks = row["subtasks"] or []
            subtasks.append({"id": str(len(subtasks)+1), "title": title, "status": "pending", "order": len(subtasks)})
            cur.execute(
                "UPDATE todos SET subtasks = %s WHERE id = %s",
                (json.dumps(subtasks), row["id"])
            )
    return {"message": "Subtask added"}
