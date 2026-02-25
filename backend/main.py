import os
from fastapi import FastAPI
from psycopg import connect
from psycopg.rows import dict_row

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
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM jobs ORDER BY created_at DESC;")
            return cur.fetchall()
@app.get("/todos")
def list_todos():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM todos ORDER BY created_at DESC;")
            return cur.fetchall()

@app.post("/jobs")
def create_job(job: dict):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (company, role, link, status, description)
                VALUES (%s, %s, %s, COALESCE(%s, 'saved'), %s)
                RETURNING *;
                """,
                (job.get("company"), job.get("role"), job.get("link"), job.get("status"), job.get("description"))
            )
            created = cur.fetchone()
        conn.commit()
    return created