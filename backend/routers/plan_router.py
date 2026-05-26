from fastapi import APIRouter
from pydantic import BaseModel
from db import get_conn

router = APIRouter(prefix="/api/v1")

PLAN_DATE = '2000-01-01'


class PlanBody(BaseModel):
    content: str


@router.get("/plan")
def get_plan():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT content FROM daily_plan WHERE plan_date = %s;", (PLAN_DATE,))
            row = cur.fetchone()
    if not row:
        return {"content": ""}
    return {"content": row["content"]}


@router.put("/plan")
def upsert_plan(body: PlanBody):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_plan (plan_date, content) VALUES (%s, %s)
                ON CONFLICT (plan_date) DO UPDATE SET content = EXCLUDED.content
                RETURNING content;
                """,
                (PLAN_DATE, body.content)
            )
            row = cur.fetchone()
        conn.commit()
    return {"content": row["content"]}
