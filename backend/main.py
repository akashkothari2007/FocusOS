from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
import os
from psycopg import connect
from psycopg.rows import dict_row
from datetime import datetime

app = FastAPI()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://focusos:focusos@localhost:5432/focusos" #fallback to local database if not set in environment variables
) 


def get_conn():
    return connect(DATABASE_URL, row_factory=dict_row)

#health check
@app.get("/health")
def health():
    return {"ok": True}

#db check

@app.get("/db")
def db_check():
    # proves backend can connect + query
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS one;")
            row = cur.fetchone()
    return {"db": "connected", "result": row}

@app.get("/jobs")
def list_jobs():
    query = """
    SELECT
      j.*,
      a.match_score,
      a.summary,
      a.updated_at AS analysis_updated_at,
      d.latest_doc_id AS tailored_doc_id
    FROM jobs j
    LEFT JOIN job_analysis a
      ON a.job_id = j.id
    LEFT JOIN (
      SELECT job_id, MAX(id) AS latest_doc_id
      FROM docs
      WHERE kind = 'tailored'
      GROUP BY job_id
    ) d
      ON d.job_id = j.id
    ORDER BY j.created_at DESC;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()

class JobCreate(BaseModel):
    company: str
    title: str
    link: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = Field(default="saved")  # or "in progress" if that's your default

@app.post("/jobs", status_code=201)
def create_job(job: JobCreate):
    query = """
    INSERT INTO jobs (company, status, link, description, title)
    VALUES (%s, COALESCE(%s, 'saved'),%s, %s, %s)
    RETURNING *;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (job.company, job.status, job.link, job.description, job.title),
            )
            created = cur.fetchone()
            conn.commit()
            return created

class JobStatusUpdate(BaseModel):
    status: Literal["saved", "in progress", "applied", "interview", "rejected"]

@app.patch("/jobs/{job_id}")
def update_job_status(job_id: int, payload: JobStatusUpdate):
    query = """
    UPDATE jobs
    SET status = %s
    WHERE id = %s
    RETURNING *;
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (payload.status, job_id))
            updated = cur.fetchone()
            if not updated:
                raise HTTPException(status_code=404, detail="Job not found")
            conn.commit()
            return updated


@app.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM jobs WHERE id = %s RETURNING id;", (job_id,))
            deleted = cur.fetchone()
            if not deleted:
                raise HTTPException(status_code=404, detail="Job not found")
            conn.commit()
            return

@app.get("/todos")
def list_todos():
    query = """
    SELECT * FROM todos
    WHERE status = 'todo'
    ORDER BY due_date ASC:
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()

class TodoCreate(BaseModel):
    title: str
    notes: Optional[str] = None
    due_date: Optional[datetime] = None

@app.post("/todos", status_code=201)
def create_todo(todo: TodoCreate):
    query = """
    INSERT INTO todos (title, notes, due_date)
    VALUES (%s, %s, %s)
    RETURNING *;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (todo.title, todo.notes, todo.due_date))
            created = cur.fetchone()
            conn.commit()
            return created
