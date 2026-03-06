from datetime import date, timedelta
from fastapi import APIRouter, HTTPException
from typing import Optional
from db import get_conn
from models.habit_models import CreateHabit, UpdateHabit, ToggleHabitLog

router = APIRouter(prefix="/api/v1")


@router.get("/habits")
def get_habits(active: Optional[bool] = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if active is not None:
                cur.execute(
                    "SELECT * FROM habits WHERE is_active = %s ORDER BY created_at ASC;",
                    (active,)
                )
            else:
                cur.execute("SELECT * FROM habits ORDER BY created_at ASC;")
            rows = cur.fetchall()
    return {"habits": rows}


@router.post("/habits", status_code=201)
def create_habit(habit: CreateHabit):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO habits (name, frequency) VALUES (%s, %s) RETURNING *;",
                (habit.name, habit.frequency)
            )
            row = cur.fetchone()
    return row


# NOTE: /habits/logs and /habits/logs/toggle must be defined BEFORE /habits/{habit_id}
# so FastAPI matches them as static paths first.

@router.get("/habits/logs")
def get_habit_logs(days: int = 7):
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    date_range = [start_date + timedelta(days=i) for i in range(days)]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM habits WHERE is_active = TRUE ORDER BY created_at ASC;"
            )
            habits = cur.fetchall()

            cur.execute(
                """
                SELECT hl.habit_id, hl.log_date, hl.completed
                FROM habit_logs hl
                JOIN habits h ON h.id = hl.habit_id
                WHERE h.is_active = TRUE
                  AND hl.log_date BETWEEN %s AND %s;
                """,
                (start_date, end_date)
            )
            logs = cur.fetchall()

            # Fetch all completed logs (for streak calculation beyond the window)
            cur.execute(
                """
                SELECT hl.habit_id, hl.log_date
                FROM habit_logs hl
                JOIN habits h ON h.id = hl.habit_id
                WHERE h.is_active = TRUE AND hl.completed = TRUE;
                """
            )
            all_completed = cur.fetchall()

    # Build lookup: {habit_id: {date_str: completed}}
    log_lookup: dict = {}
    for log in logs:
        hid = log["habit_id"]
        d_str = str(log["log_date"])
        if hid not in log_lookup:
            log_lookup[hid] = {}
        log_lookup[hid][d_str] = log["completed"]

    # Build completed date sets per habit for streak calculation
    completed_sets: dict = {}
    for row in all_completed:
        hid = row["habit_id"]
        if hid not in completed_sets:
            completed_sets[hid] = set()
        completed_sets[hid].add(row["log_date"])

    def compute_streak(completed_dates: set, today: date) -> int:
        start = today if today in completed_dates else today - timedelta(days=1)
        if start not in completed_dates:
            return 0
        streak = 0
        current = start
        while current in completed_dates:
            streak += 1
            current -= timedelta(days=1)
        return streak

    # Current Mon–Sun week bounds
    week_start = end_date - timedelta(days=end_date.weekday())
    week_end = week_start + timedelta(days=6)

    result = []
    for habit in habits:
        grid = [
            {"date": str(d), "completed": log_lookup.get(habit["id"], {}).get(str(d), False)}
            for d in date_range
        ]
        completed = completed_sets.get(habit["id"], set())
        streak = compute_streak(completed, end_date)
        week_count = sum(1 for d in completed if week_start <= d <= week_end)
        result.append({
            "id": habit["id"],
            "name": habit["name"],
            "is_active": habit["is_active"],
            "frequency": habit["frequency"],
            "grid": grid,
            "streak": streak,
            "week_count": week_count,
        })

    return {"habits": result, "dates": [str(d) for d in date_range]}


@router.post("/habits/logs/toggle")
def toggle_habit_log(body: ToggleHabitLog):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM habits WHERE id = %s;", (body.habit_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Habit not found")

            cur.execute(
                """
                INSERT INTO habit_logs (habit_id, log_date, completed)
                VALUES (%s, %s, TRUE)
                ON CONFLICT (habit_id, log_date)
                DO UPDATE SET completed = NOT habit_logs.completed
                RETURNING *;
                """,
                (body.habit_id, body.log_date)
            )
            row = cur.fetchone()
    return row


@router.patch("/habits/{habit_id}")
def update_habit(habit_id: int, updates: UpdateHabit):
    fields = updates.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [habit_id]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE habits SET {set_clause} WHERE id = %s RETURNING *;",
                values
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Habit not found")
    return row


@router.delete("/habits/{habit_id}", status_code=204)
def delete_habit(habit_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM habits WHERE id = %s RETURNING id;", (habit_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Habit not found")
    return
