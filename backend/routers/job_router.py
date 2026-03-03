import json
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional, Literal

from db import get_conn
from models.job_models import CreateJob, UpdateJob, AnalyzeJob
from ai import chat_json, fmt_profile
from prompts import summary_messages, step1_messages, step2_messages, resume_messages

router = APIRouter(prefix="/api/v1")

# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

def generate_summary(job_id: int, description: str) -> None:
    """Summarize a job description and patch jobs.summary + analysis_status."""
    try:
        data = chat_json(summary_messages(description))
        summary = data["summary"]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET summary = %s, analysis_status = 'idle' WHERE id = %s;",
                    (summary, job_id),
                )
    except Exception as e:
        print(f"SUMMARY ERROR job {job_id}: {type(e).__name__}: {e}", flush=True)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'error' WHERE id = %s;",
                    (job_id,),
                )


def run_analysis(job_id: int, input_doc_id: int) -> None:
    """Two-step AI analysis: (1) match score + keywords, (2) resume suggestions."""

    # Mark in-progress
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET analysis_status = 'analyzing' WHERE id = %s;",
                (job_id,),
            )

    # Fetch required data
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT description, summary FROM jobs WHERE id = %s;", (job_id,)
            )
            job = cur.fetchone()
            cur.execute("SELECT content FROM docs WHERE id = %s;", (input_doc_id,))
            doc = cur.fetchone()
            cur.execute("SELECT projects, experiences FROM profile WHERE id = 1;")
            profile = cur.fetchone()

    if not job or not doc:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'error' WHERE id = %s;", (job_id,)
                )
        return

    profile_ctx = fmt_profile(profile)

    # --- Step 1: match_score + keywords ---
    try:
        data = chat_json(step1_messages(job["description"], doc["content"], profile_ctx))
        match_score = int(data["match_score"])
        keywords = list(data["keywords"])
    except Exception:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'error' WHERE id = %s;", (job_id,)
                )
        return  # Abort: step 1 is required

    # Surface step-1 results immediately
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_analysis
                SET match_score = %s, keywords = %s, updated_at = NOW()
                WHERE job_id = %s;
                """,
                (match_score, json.dumps(keywords), job_id),
            )

    # --- Step 2: suggestions ---
    suggestions = []
    try:
        data = chat_json(step2_messages(keywords, job["description"], doc["content"], profile_ctx))
        suggestions = list(data["suggestions"])
    except Exception:
        pass  # Step 2 failure is non-fatal

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_analysis
                SET suggestions = %s, updated_at = NOW()
                WHERE job_id = %s;
                """,
                (json.dumps(suggestions), job_id),
            )
            cur.execute(
                "UPDATE jobs SET analysis_status = 'done' WHERE id = %s;",
                (job_id,),
            )

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/jobs")
def get_jobs(status: Optional[Literal["saved", "applied", "interview", "rejected"]] = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    "SELECT * FROM jobs WHERE status = %s ORDER BY created_at DESC;",
                    (status,),
                )
            else:
                cur.execute("SELECT * FROM jobs ORDER BY created_at DESC;")
            rows = cur.fetchall()
    return {"jobs": rows}


@router.get("/jobs/{job_id}")
def get_job(job_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT j.*,
                       ja.input_doc_id, ja.output_doc_id, ja.match_score,
                       ja.keywords, ja.suggestions, ja.updated_at AS analysis_updated_at
                FROM jobs j
                LEFT JOIN job_analysis ja ON ja.job_id = j.id
                WHERE j.id = %s;
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")
    return row


@router.post("/jobs", status_code=201)
def create_job(job: CreateJob, bg: BackgroundTasks):
    analysis_status = "summarizing" if job.description else "idle"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (title, company, status, link, description, analysis_status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (job.title, job.company, job.status, job.link, job.description, analysis_status),
            )
            row = cur.fetchone()

    if job.description:
        bg.add_task(generate_summary, row["id"], job.description)

    return row


@router.patch("/jobs/{job_id}")
def update_job(job_id: int, updates: UpdateJob):
    fields = updates.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [job_id]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE jobs SET {set_clause} WHERE id = %s RETURNING *;",
                values,
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Job not found")
    return row


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM jobs WHERE id = %s RETURNING id;", (job_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Job not found")
    return


@router.post("/jobs/{job_id}/analyze", status_code=201)
def analyze_job(job_id: int, body: AnalyzeJob, bg: BackgroundTasks):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM jobs WHERE id = %s;", (job_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Job not found")

            cur.execute(
                """
                INSERT INTO job_analysis (job_id, input_doc_id, match_score, keywords, suggestions, updated_at)
                VALUES (%s, %s, 0, '[]', '[]', NOW())
                ON CONFLICT (job_id) DO UPDATE SET
                    input_doc_id = EXCLUDED.input_doc_id,
                    match_score  = 0,
                    keywords     = '[]',
                    suggestions  = '[]',
                    updated_at   = NOW()
                RETURNING *;
                """,
                (job_id, body.input_doc_id),
            )
            row = cur.fetchone()

    bg.add_task(run_analysis, job_id, body.input_doc_id)
    return row


@router.delete("/jobs/{job_id}/analysis", status_code=204)
def delete_analysis(job_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM job_analysis WHERE job_id = %s RETURNING job_id;",
                (job_id,),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Analysis not found")
    return


def generate_resume_bg(job_id: int) -> None:
    """Generate a tailored LaTeX resume and save it as a new doc."""
    try:
        # Mark in-progress
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'generating_resume' WHERE id = %s;",
                    (job_id,),
                )

        # Fetch all required data
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT title, company, description FROM jobs WHERE id = %s;",
                    (job_id,),
                )
                job = cur.fetchone()
                cur.execute(
                    "SELECT input_doc_id, keywords, suggestions FROM job_analysis WHERE job_id = %s;",
                    (job_id,),
                )
                analysis = cur.fetchone()
                cur.execute(
                    "SELECT content FROM docs WHERE id = %s;",
                    (analysis["input_doc_id"],),
                )
                doc = cur.fetchone()
                cur.execute("SELECT projects, experiences FROM profile WHERE id = 1;")
                profile = cur.fetchone()

        profile_ctx = fmt_profile(profile)
        keywords = analysis["keywords"] or []
        suggestions = analysis["suggestions"] or []

        data = chat_json(
            resume_messages(
                base_resume=doc["content"],
                keywords=keywords,
                suggestions=suggestions,
                profile_ctx=profile_ctx,
                job_description=job["description"] or "",
            )
        )
        latex = data["resume"]

        doc_title = f"{job['title']} @ {job['company']} \u2014 Tailored"

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO docs (title, content) VALUES (%s, %s) RETURNING id;",
                    (doc_title, latex),
                )
                new_doc_id = cur.fetchone()["id"]
                cur.execute(
                    "UPDATE job_analysis SET output_doc_id = %s, updated_at = NOW() WHERE job_id = %s;",
                    (new_doc_id, job_id),
                )
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'done' WHERE id = %s;",
                    (job_id,),
                )

    except Exception as e:
        print(f"RESUME ERROR job {job_id}: {type(e).__name__}: {e}", flush=True)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'error' WHERE id = %s;",
                    (job_id,),
                )


@router.post("/jobs/{job_id}/generate-resume")
def generate_resume(job_id: int, bg: BackgroundTasks):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT analysis_status FROM jobs WHERE id = %s;", (job_id,)
            )
            job = cur.fetchone()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            cur.execute(
                "SELECT input_doc_id FROM job_analysis WHERE job_id = %s;", (job_id,)
            )
            analysis = cur.fetchone()
            if not analysis or not analysis["input_doc_id"]:
                raise HTTPException(status_code=400, detail="No analysis found — run /analyze first")

    bg.add_task(generate_resume_bg, job_id)
    return {"message": "generating"}
