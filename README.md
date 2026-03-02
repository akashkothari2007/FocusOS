# FocusOS

Personal operations dashboard for:
- Keeping track of jobs
- Tailoring resumes for each job, and rating the match
- Research / interview prep
- Tasks / todos
- Email-based action tracking (add to todos)

---

## V1 (right now)

A full-stack web app that:

- Tracks job applications and their status
- Stores job descriptions
- Uses AI to:
  - Summarize job postings
  - Score resume match
  - Suggest resume improvements
- Manages personal tasks in one place

Primary goal:
Build strong backend architecture and real-world automation logic.

---

## Start the Service

Requirements:
- Docker
- npm

Run:
docker compose up -d --build
cd testfrontend (seperate for now will dockerize real frontend later)
npm run dev

Services:
- Backend: http://localhost:8000
- PostgreSQL: localhost:5432
- Frontend: localhost:5173

View logs:
docker compose logs -f backend
docker compose logs -f db

Test endpoints:
curl http://localhost:8000/health
curl http://localhost:8000/db

---

## What I Will Add Later (V2+)

- Background task processing (async AI jobs)
- Resume generation in LaTeX (tailored per job)
- Company research module
- Email scanning (auto-detect interview/rejection emails and create tasks)
- Scheduled workflows (daily scans, reminders)
- Analytics dashboard (applications, response rates, trends)

Long-term direction:
Evolve into a personal AI system that manages applications, tasks, and decision-making workflows. My personal assistant.

---

## Database Diagram

[Link for DB](https://dbdiagram.io/d/69a1d6fea3f0aa31e155e8b0)

## Tech Stack

Frontend:
- React (Vite)

Backend:
- FastAPI (Python)

Database:
- PostgreSQL

Dev Environment:
- Docker

Future Additions:
- Redis (for background job queue if async AI processing becomes necessary)
- Background workers for scheduled tasks
- Cloud deployment (TBD)