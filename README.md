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

## What We Will Add Later (V2+)

- Background task processing (async AI jobs)
- Resume generation in LaTeX (tailored per job)
- Company research module
- Email scanning (auto-detect interview/rejection emails and create tasks)
- Scheduled workflows (daily scans, reminders)
- Analytics dashboard (applications, response rates, trends)

Long-term direction:
Evolve into a personal AI system that manages applications, tasks, and decision-making workflows. My personal assistant.

---

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