"""FocusOS MCP Server — wraps the deployed FastAPI backend."""

import asyncio
import httpx
import os
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

BASE_URL = os.environ.get("FOCUSOS_URL", "http://localhost:8000")
API_KEY = os.environ.get("FOCUSOS_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

server = Server("focusos")


def api(method: str, path: str, **kwargs):
    with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=15) as client:
        r = client.request(method, path, **kwargs)
        r.raise_for_status()
        if r.status_code == 204:
            return {}
        return r.json()


def fuzzy_find_todo(todos: list, query: str):
    """Find best matching todo by title (case-insensitive substring)."""
    q = query.lower()
    for t in todos:
        if q in t["title"].lower():
            return t
    # fallback: any word overlap
    words = set(q.split())
    best, best_score = None, 0
    for t in todos:
        score = sum(1 for w in words if w in t["title"].lower())
        if score > best_score:
            best, best_score = t, score
    return best if best_score > 0 else None


@server.list_tools()
async def list_tools():
    return [
        # ── Todos ──────────────────────────────────────────────────────────
        types.Tool(
            name="get_todos",
            description="List all pending todos with their subtasks",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_todo_details",
            description="Get full details (subtasks, description, links) for a todo by name",
            inputSchema={
                "type": "object",
                "properties": {"project": {"type": "string", "description": "Todo name (fuzzy match)"}},
                "required": ["project"],
            },
        ),
        types.Tool(
            name="create_todo",
            description="Create a new todo, optionally with a description and subtasks",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "subtasks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of subtask titles to create",
                    },
                },
                "required": ["title"],
            },
        ),
        types.Tool(
            name="complete_todo",
            description="Mark a todo as done by ID",
            inputSchema={
                "type": "object",
                "properties": {"todo_id": {"type": "integer"}},
                "required": ["todo_id"],
            },
        ),
        # ── Subtasks ───────────────────────────────────────────────────────
        types.Tool(
            name="add_subtask",
            description="Add a subtask to a todo by fuzzy project name",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "project": {"type": "string"},
                },
                "required": ["title", "project"],
            },
        ),
        types.Tool(
            name="complete_subtask",
            description="Mark a subtask as done within a todo (fuzzy match on both todo and subtask title)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {"type": "string", "description": "Todo name (fuzzy)"},
                    "subtask": {"type": "string", "description": "Subtask title (fuzzy)"},
                },
                "required": ["project", "subtask"],
            },
        ),
        # ── Sessions ───────────────────────────────────────────────────────
        types.Tool(
            name="get_active_session",
            description="Get the currently active session if any",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="start_session",
            description="Start a work session. Fuzzy-matches a todo by name, or starts a freeform session if no match.",
            inputSchema={
                "type": "object",
                "properties": {"project": {"type": "string"}},
                "required": ["project"],
            },
        ),
        types.Tool(
            name="end_session",
            description="End the current active session, optionally with closing notes",
            inputSchema={
                "type": "object",
                "properties": {"notes": {"type": "string", "description": "Optional closing notes"}},
            },
        ),
        types.Tool(
            name="append_session_notes",
            description="Append text to the current active session's notes (non-destructive, keeps existing notes)",
            inputSchema={
                "type": "object",
                "properties": {"notes": {"type": "string"}},
                "required": ["notes"],
            },
        ),
        types.Tool(
            name="get_sessions_today",
            description="Get all sessions worked on today",
            inputSchema={"type": "object", "properties": {}},
        ),
        # ── Habits ─────────────────────────────────────────────────────────
        types.Tool(
            name="get_habits",
            description="Get all active habits with today's completion status and streaks",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="toggle_habit",
            description="Toggle a habit as completed for today (fuzzy match by name)",
            inputSchema={
                "type": "object",
                "properties": {"habit": {"type": "string", "description": "Habit name (fuzzy)"}},
                "required": ["habit"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        # ── Todos ──────────────────────────────────────────────────────────
        if name == "get_todos":
            data = api("GET", "/api/v1/todos", params={"status": "pending"})
            todos = data.get("todos", [])
            if not todos:
                result = "No pending todos"
            else:
                lines = []
                for t in todos:
                    due = t.get("due_date") or "no due date"
                    subtasks = t.get("subtasks") or []
                    pending_sub = [s for s in subtasks if s.get("status") != "done"]
                    sub_str = f" [{len(pending_sub)} subtasks]" if pending_sub else ""
                    lines.append(f"#{t['id']} {t['title']} (due: {due}){sub_str}")
                result = "\n".join(lines)

        elif name == "get_todo_details":
            data = api("GET", "/api/v1/todos", params={"status": "pending"})
            todo = fuzzy_find_todo(data.get("todos", []), arguments["project"])
            if not todo:
                result = f"No todo matching '{arguments['project']}'"
            else:
                subtasks = todo.get("subtasks") or []
                sub_lines = []
                for s in subtasks:
                    icon = "✓" if s.get("status") == "done" else "○"
                    sub_lines.append(f"  {icon} {s['title']}")
                desc = todo.get("description") or "(no description)"
                links = todo.get("links") or []
                link_str = ", ".join(f"{l['title']}: {l['url']}" for l in links) if links else ""
                result = f"#{todo['id']} {todo['title']}\nDescription: {desc}"
                if sub_lines:
                    result += "\nSubtasks:\n" + "\n".join(sub_lines)
                if link_str:
                    result += f"\nLinks: {link_str}"

        elif name == "create_todo":
            subtask_titles = arguments.get("subtasks", [])
            subtasks_payload = [{"id": i + 1, "title": t, "status": "pending", "order": i}
                                 for i, t in enumerate(subtask_titles)]
            payload = {"title": arguments["title"]}
            if arguments.get("description"):
                payload["description"] = arguments["description"]
            if subtasks_payload:
                payload["subtasks"] = subtasks_payload
            data = api("POST", "/api/v1/todos", json=payload)
            sub_note = f" with {len(subtask_titles)} subtasks" if subtask_titles else ""
            result = f"Created todo #{data['id']}: {data['title']}{sub_note}"

        elif name == "complete_todo":
            api("PATCH", f"/api/v1/todos/{arguments['todo_id']}", json={"status": "done"})
            result = f"Marked todo #{arguments['todo_id']} as done"

        # ── Subtasks ───────────────────────────────────────────────────────
        elif name == "add_subtask":
            api("POST", "/api/v1/todos/quick-subtask",
                json={"title": arguments["title"], "project": arguments["project"]})
            result = f"Added subtask '{arguments['title']}' to {arguments['project']}"

        elif name == "complete_subtask":
            data = api("GET", "/api/v1/todos", params={"status": "pending"})
            todo = fuzzy_find_todo(data.get("todos", []), arguments["project"])
            if not todo:
                result = f"No todo matching '{arguments['project']}'"
            else:
                subtasks = todo.get("subtasks") or []
                sq = arguments["subtask"].lower()
                match = next((s for s in subtasks if sq in s["title"].lower()), None)
                if not match:
                    result = f"No subtask matching '{arguments['subtask']}' in {todo['title']}"
                else:
                    match["status"] = "done"
                    api("PATCH", f"/api/v1/todos/{todo['id']}", json={"subtasks": subtasks})
                    result = f"✓ Completed subtask '{match['title']}' in {todo['title']}"

        # ── Sessions ───────────────────────────────────────────────────────
        elif name == "get_active_session":
            data = api("GET", "/api/v1/sessions/active")
            if data:
                title = data.get("todo_title") or data.get("title") or "Untitled"
                secs = data.get("seconds_spent") or 0
                notes = data.get("notes") or "(no notes)"
                result = f"Active: '{title}' — {secs // 60}m {secs % 60}s\nNotes: {notes}"
            else:
                result = "No active session"

        elif name == "start_session":
            data = api("POST", "/api/v1/todos/quick-session", json={"project": arguments["project"]})
            if data.get("status") == "skipped":
                result = "Session already active — end it first"
            else:
                result = f"Started session: '{data.get('title')}'"

        elif name == "end_session":
            closing_notes = arguments.get("notes")
            if closing_notes:
                session = api("GET", "/api/v1/sessions/active")
                if session:
                    existing = session.get("notes") or ""
                    merged = (existing + "\n" + closing_notes).strip()
                    api("PATCH", f"/api/v1/sessions/{session['id']}/end", json={"notes": merged})
                    data = {"title": session.get("title"), "seconds_spent": session.get("seconds_spent")}
                else:
                    data = api("POST", "/api/v1/sessions/quick-end")
            else:
                data = api("POST", "/api/v1/sessions/quick-end")
            if data.get("status") == "skipped":
                result = "No active session to end"
            else:
                secs = data.get("seconds_spent") or 0
                result = f"Ended '{data.get('title')}' — {secs // 60}m {secs % 60}s"

        elif name == "append_session_notes":
            session = api("GET", "/api/v1/sessions/active")
            if not session:
                result = "No active session"
            else:
                existing = session.get("notes") or ""
                new_notes = (existing + "\n" + arguments["notes"]).strip()
                api("PATCH", f"/api/v1/sessions/{session['id']}/notes", json={"notes": new_notes})
                result = "Notes updated"

        elif name == "get_sessions_today":
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            data = api("GET", "/api/v1/sessions/today",
                       params={"start": start.isoformat(), "end": end.isoformat()})
            sessions = data if isinstance(data, list) else data.get("sessions", [])
            if not sessions:
                result = "No sessions today"
            else:
                lines = []
                total = 0
                for s in sessions:
                    title = s.get("todo_title") or s.get("title") or "Untitled"
                    secs = s.get("seconds_spent") or 0
                    total += secs
                    status = "● active" if not s.get("ended_at") else f"{secs // 60}m {secs % 60}s"
                    lines.append(f"  {title}: {status}")
                result = f"Today ({total // 60}m total):\n" + "\n".join(lines)

        # ── Habits ─────────────────────────────────────────────────────────
        elif name == "get_habits":
            from datetime import date
            today = date.today().isoformat()
            data = api("GET", "/api/v1/habits/logs", params={"days": 7, "today": today})
            habits = data.get("habits", [])
            if not habits:
                result = "No active habits"
            else:
                lines = []
                for h in habits:
                    done_today = h.get("today_done", False)
                    streak = h.get("streak", 0)
                    icon = "✓" if done_today else "○"
                    lines.append(f"{icon} {h['name']} (streak: {streak})")
                result = "\n".join(lines)

        elif name == "toggle_habit":
            from datetime import date
            today_str = date.today().isoformat()
            # get all habits to find ID
            habits_data = api("GET", "/api/v1/habits", params={"active": "true"})
            habits = habits_data if isinstance(habits_data, list) else habits_data.get("habits", [])
            q = arguments["habit"].lower()
            match = next((h for h in habits if q in h["name"].lower()), None)
            if not match:
                result = f"No habit matching '{arguments['habit']}'"
            else:
                api("POST", "/api/v1/habits/logs/toggle",
                    json={"habit_id": match["id"], "log_date": today_str})
                result = f"Toggled habit '{match['name']}' for today"

        else:
            result = f"Unknown tool: {name}"

    except Exception as e:
        result = f"Error: {e}"

    return [types.TextContent(type="text", text=result)]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
