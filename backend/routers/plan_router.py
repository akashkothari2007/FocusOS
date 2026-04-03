from fastapi import APIRouter
from pydantic import BaseModel
from db import get_conn

router = APIRouter(prefix="/api/v1")


class DailyPlanBody(BaseModel):
    date: str
    content: str


@router.get("/daily-plan")
def get_daily_plan(date: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT plan_date::text AS date, content FROM daily_plan WHERE plan_date = %s;", (date,))
            row = cur.fetchone()
    if not row:
        return {"date": date, "content": ""}
    return row


@router.put("/daily-plan")
def upsert_daily_plan(body: DailyPlanBody):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_plan (plan_date, content) VALUES (%s, %s)
                ON CONFLICT (plan_date) DO UPDATE SET content = EXCLUDED.content
                RETURNING plan_date::text AS date, content;
                """,
                (body.date, body.content)
            )
            row = cur.fetchone()
        conn.commit()
    return row
