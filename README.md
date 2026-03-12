# FocusOS

Personal operations dashboard. Built to manage job applications, tasks, work sessions, habits, and AI-assisted resume tailoring — all in one place.

---

## What It Does

- **Todos** — task management with subtasks, due dates, drag-to-reorder, and session tracking
- **Work Sessions** — start/stop timed sessions linked to todos (or freeform), view on a week calendar
- **Job Portal** — track applications, store job descriptions, AI-generated summaries and resume analysis
- **Resume / Docs** — store LaTeX resumes, auto-generate tailored versions per job via AI
- **Profile** — store projects, experiences, and skills used as context for AI analysis
- **Habit Tracker** — daily/weekly habit grid with streaks and metrics
- **Metrics** — session history grouped by todo, habit completion rates
- **Email Integration** — Microsoft OAuth email scanning (scheduled 8am/6pm ET)

---

## Stack

| Layer     | Tech                                          |
|-----------|-----------------------------------------------|
| Frontend  | React (Vite), plain CSS                       |
| Backend   | FastAPI (Python), APScheduler                 |
| Database  | PostgreSQL 16                                 |
| AI        | OpenAI API (`chat_json` wrapper)              |
| Dev Env   | Docker Compose (backend + db)                 |
| Deploy    | Railway (backend), Vite dev server (frontend) |

---

## Running Locally

**Requirements:** Docker, Node.js

```bash
# Start backend + database
docker compose up -d --build

# Start frontend (dev)
cd testfrontend
npm install
npm run dev
```

**Services:**
- Backend API: http://localhost:8000
- Frontend: http://localhost:5173
- PostgreSQL: localhost:5432

**Health checks:**
```bash
curl http://localhost:8000/health
curl http://localhost:8000/db
```

**Logs:**
```bash
docker compose logs -f backend
docker compose logs -f db
```

---

## Environment Variables

Create `backend/.env`:

```env
DATABASE_URL=postgresql://focusos:focusos@db:5432/focusos
FOCUSOS_API_KEY=your_api_key_here
OPENAI_API_KEY=your_openai_key
# Microsoft OAuth (for email scanning):
MS_CLIENT_ID=
MS_CLIENT_SECRET=
MS_REDIRECT_URI=
MS_USER_EMAIL=
```

Frontend: create `testfrontend/.env`:
```env
VITE_FOCUSOS_API_KEY=your_api_key_here
```

---

## Auth

All API routes (except `/health`, `/db`, `/auth/login`, `/auth/callback`) require:
```
X-API-Key: <FOCUSOS_API_KEY>
```

---

## Project Structure

```
FocusOS/
├── backend/
│   ├── main.py              # FastAPI app, middleware, scheduler startup
│   ├── db.py                # psycopg3 connection (row_factory=dict_row)
│   ├── ai.py                # OpenAI wrapper (chat_json)
│   ├── prompts.py           # AI prompt builders (summary, analysis, resume)
│   ├── scheduler.py         # Email scan job (runs 8am/6pm ET)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── routers/
│   │   ├── todo_router.py
│   │   ├── session_router.py
│   │   ├── job_router.py
│   │   ├── doc_router.py
│   │   ├── profile_router.py
│   │   ├── habit_router.py
│   │   └── email_router.py
│   ├── models/              # Pydantic request/response models
│   └── jobs/                # Resume parsing (latex_handler, resume_injector)
├── testfrontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js           # All API calls (proxied via vite.config.js)
│   │   ├── pages/
│   │   │   ├── Todos.jsx
│   │   │   ├── Calendar.jsx
│   │   │   ├── Metrics.jsx
│   │   │   ├── Jobs.jsx
│   │   │   ├── Docs.jsx
│   │   │   └── Profile.jsx
│   │   ├── components/
│   │   │   ├── TodoCard.jsx
│   │   │   ├── AddTodoForm.jsx
│   │   │   ├── SessionBar.jsx
│   │   │   ├── HabitTracker.jsx
│   │   │   └── TodayStrip.jsx
│   │   └── styles/app.css
│   └── vite.config.js       # Proxy: /api + /auth → Railway backend
└── docker-compose.yml
```

---

## API Reference

All routes prefixed `/api/v1`.

### Todos
| Method | Path | Description |
|--------|------|-------------|
| GET | `/todos` | List all (optional `?status=pending\|done`) |
| POST | `/todos` | Create todo |
| PATCH | `/todos/{id}` | Partial update |
| DELETE | `/todos/{id}` | Delete |
| POST | `/todos/reorder` | Reorder undated todos |
| GET | `/todos/{id}/sessions` | Get sessions for a todo |
| POST | `/todos/{id}/sessions/start` | Start linked session |

### Sessions
| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions/active` | Get open session (if any) |
| POST | `/sessions/start` | Start freeform session |
| PATCH | `/sessions/{id}/end` | End session |
| DELETE | `/sessions/{id}` | Delete session |
| GET | `/sessions/today` | Sessions for a day (`?start=&end=` UTC ISO) |
| GET | `/sessions/week` | Sessions for a week (`?start=&end=` UTC ISO) |

### Jobs
| Method | Path | Description |
|--------|------|-------------|
| GET | `/jobs` | List all (optional `?status=`) |
| GET | `/jobs/{id}` | Get job + analysis |
| POST | `/jobs` | Create (triggers AI summary in background) |
| PATCH | `/jobs/{id}` | Update |
| DELETE | `/jobs/{id}` | Delete |
| POST | `/jobs/{id}/analyze` | Run AI analysis (background) |
| DELETE | `/jobs/{id}/analysis` | Clear analysis |
| POST | `/jobs/{id}/generate-resume` | Generate tailored LaTeX resume (background) |

### Docs
| Method | Path | Description |
|--------|------|-------------|
| GET | `/docs` | List all |
| POST | `/docs` | Create |
| PATCH | `/docs/{id}` | Update |
| PATCH | `/docs/{id}/set-primary` | Mark as primary resume |
| DELETE | `/docs/{id}` | Delete |

### Profile
| Method | Path | Description |
|--------|------|-------------|
| GET | `/profile` | Get profile (single row) |
| PATCH | `/profile` | Update profile |

### Habits
| Method | Path | Description |
|--------|------|-------------|
| GET | `/habits` | List all (optional `?active=true`) |
| POST | `/habits` | Create habit |
| PATCH | `/habits/{id}` | Update habit |
| DELETE | `/habits/{id}` | Delete habit |
| GET | `/habits/logs` | Get grid + streaks (`?days=7&today=YYYY-MM-DD`) |
| POST | `/habits/logs/toggle` | Toggle a day's completion |

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | `{"ok": true}` |
| GET | `/db` | DB connectivity check |

---

## DB Diagram

[dbdiagram.io](https://dbdiagram.io/d/69a1d6fea3f0aa31e155e8b0)

---

## Roadmap

- Analytics dashboard (time trends, application conversion rates)
- Scheduled reminders / digest emails
- Cloud deployment (custom domain + auth)
- Redis background queue for heavier AI jobs
