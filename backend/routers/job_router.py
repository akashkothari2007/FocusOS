import json
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional, Literal

from db import get_conn
from models.job_models import CreateJob, UpdateJob, AnalyzeJob
from ai import chat_json
from latex_handler import fmt_profile, parse_latex
from prompts import summary_messages, analysis_messages, resume_messages
from resume_injector import inject_changes

log = logging.getLogger("job_router")
router = APIRouter(prefix="/api/v1")

SEP = "─" * 50

# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

def generate_summary_and_keywords(job_id: int, description: str) -> None:
    try:
        data = chat_json(summary_messages(description))
        summary = data.get("summary", "")
        keywords = data.get("keywords", [])
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET summary = %s, keywords = %s, analysis_status = 'idle' WHERE id = %s;",
                    (summary, json.dumps(keywords), job_id),
                )
    except Exception as e:
        log.error(f"[SUMMARY] job {job_id} failed: {type(e).__name__}: {e}", exc_info=True)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'error' WHERE id = %s;",
                    (job_id,),
                )


def run_analysis(job_id: int, input_doc_id: int) -> None:
    log.info(SEP)
    log.info(f"  ANALYZE  job_id={job_id}  doc_id={input_doc_id}")
    log.info(SEP)

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
            cur.execute("SELECT summary, keywords FROM jobs WHERE id = %s;", (job_id,))
            job = cur.fetchone()
            cur.execute("SELECT content FROM docs WHERE id = %s;", (input_doc_id,))
            doc = cur.fetchone()
            cur.execute("SELECT projects, experiences FROM profile WHERE id = 1;")
            profile = cur.fetchone()

    if not job or not doc:
        log.error(f"  ERROR: job={job is not None}  doc={doc is not None} — aborting")
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE jobs SET analysis_status = 'error' WHERE id = %s;", (job_id,))
        return

    log.info(f"  Job summary  : {len(job.get('summary') or '')} chars")
    log.info(f"  Job keywords : {len(job.get('keywords') or '')} chars")
    log.info(f"  Resume (doc) : {len(doc.get('content') or '')} chars")

    # Parse resume into structured plain text (no LaTeX noise)
    parsed = parse_latex(doc["content"])
    log.info(f"  Parsed       : {len(parsed['experiences'])} experiences, {len(parsed['projects'])} projects")

    # Only pass profile projects NOT already on the resume
    resume_titles = {p.title for p in parsed["projects"]}
    extra = [p for p in (profile.get("projects") or []) if p.get("title") not in resume_titles]
    extra_ctx = fmt_profile({"projects": extra, "experiences": []})
    log.info(f"  Extra profile projects for swap: {len(extra)}")

    # --- Step 2: structured suggestions ---
    log.info("")
    log.info("Generating match score and structured suggestions...")
    suggestions = {}
    match_score = 0
    try:
        data = chat_json(analysis_messages(
            keywords=job["keywords"],
            job_summary=job["summary"],
            parsed=parsed,
            profile_ctx=extra_ctx,
            n_projects=len(parsed["projects"]),
        ))
        match_score = int(data["match_score"])
        suggestions = {k: v for k, v in data.items() if k != "match_score"}
        log.info(f"  Match score  : {match_score}/100")
        log.info(f"  experience_notes: {len(suggestions.get('experience_notes', []))}")
        log.info(f"  project_plan    : {len(suggestions.get('project_plan', []))}")
    except Exception as e:
        log.error(f"  ERROR in step 2 (non-fatal): {type(e).__name__}: {e}", exc_info=True)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE job_analysis
                SET match_score = %s, suggestions = %s, updated_at = NOW()
                WHERE job_id = %s;
                """,
                (match_score, json.dumps(suggestions), job_id),
            )
            cur.execute(
                "UPDATE jobs SET analysis_status = 'done' WHERE id = %s;",
                (job_id,),
            )

    log.info("")
    log.info(f"  DONE — analysis complete for job {job_id}")
    log.info(SEP)

def generate_resume_bg(job_id: int) -> None:
    log.info(SEP)
    log.info(f"  GENERATE RESUME  job_id={job_id}")
    log.info(SEP)

    try:
        # set status to generating_resume
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'generating_resume' WHERE id = %s;",
                    (job_id,),
                )

        # fetch job and analysis
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT title, company, summary, keywords FROM jobs WHERE id = %s;", (job_id,))
                job = cur.fetchone()
                cur.execute("SELECT input_doc_id, suggestions FROM job_analysis WHERE job_id = %s;", (job_id,))
                analysis = cur.fetchone()

        if not job or not analysis:
            log.error(f"  ERROR: job={job is not None}  analysis={analysis is not None} — aborting")
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE jobs SET analysis_status = 'error' WHERE id = %s;", (job_id,))
            return

        # fetch base resume and profile
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT content FROM docs WHERE id = %s;", (analysis["input_doc_id"],))
                doc = cur.fetchone()
                cur.execute("SELECT projects, experiences FROM profile WHERE id = 1;")
                profile = cur.fetchone()

        log.info(f"  Job         : {job['title']} @ {job['company']}")
        log.info(f"  Base resume : {len(doc.get('content') or '')} chars  (doc {analysis['input_doc_id']})")

        keywords = job["keywords"] or []
        suggestions_raw = analysis["suggestions"] or {}

        # Parse resume into structured data
        parsed = parse_latex(doc["content"])
        log.info(f"  Parsed      : {len(parsed['experiences'])} experiences, {len(parsed['projects'])} projects")

        # Backward compat: old suggestions stored as flat list
        if isinstance(suggestions_raw, list):
            log.info("  [compat] old flat suggestions — using keep-all project plan with no notes")
            project_plan = [{"action": "keep", "title": p.title, "notes": []} for p in parsed["projects"]]
            suggestions_dict = {"experience_notes": [], "project_plan": project_plan}
            new_profile_projects = []
        else:
            suggestions_dict = suggestions_raw
            project_plan = suggestions_dict.get("project_plan", [])
            swap_titles = {s["add"].lower() for s in project_plan if s.get("action") == "swap"}
            new_profile_projects = [
                p for p in (profile.get("projects") or []) if p.get("title", "").lower() in swap_titles
            ]

        log.info(f"  Keywords    : {len(keywords)}")
        log.info(f"  project_plan: {len(project_plan)} entries  (swaps: {sum(1 for p in project_plan if p.get('action') == 'swap')})")
        log.info(f"  swap-in projects: {[p.get('title') for p in new_profile_projects]}")
        log.info("")
        log.info("  Calling AI for bullet rewrites (no LaTeX in/out)...")

        data = chat_json(
            resume_messages(
                keywords=keywords,
                parsed=parsed,
                suggestions=suggestions_dict,
                new_profile_projects=new_profile_projects,
            )
        )
        log.info(f"  AI output   : {len(data.get('experiences', []))} exp, {len(data.get('projects', []))} proj")

        log.info("  Injecting changes into base LaTeX...")
        latex = inject_changes(doc["content"], data, project_plan)
        log.info(f"  LaTeX final : {len(latex)} chars")

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

        log.info(f"  Saved as doc id={new_doc_id}  title={doc_title!r}")
        log.info("")
        log.info(f"  DONE — resume generated for job {job_id}")
        log.info(SEP)

    except Exception as e:
        log.error(f"  ERROR: {type(e).__name__}: {e}", exc_info=True)
        log.info(SEP)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'error' WHERE id = %s;",
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
                       ja.suggestions, ja.updated_at AS analysis_updated_at
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

#CREATE A JOB, START GENERATE_SUMMARY BACKGROUND TASK
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
        bg.add_task(generate_summary_and_keywords, row["id"], job.description)

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
                INSERT INTO job_analysis (job_id, input_doc_id, match_score, suggestions, updated_at)
                VALUES (%s, %s, 0, '[]', NOW())
                ON CONFLICT (job_id) DO UPDATE SET
                    input_doc_id = EXCLUDED.input_doc_id,
                    match_score  = 0,
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



@router.post("/jobs/{job_id}/generate-resume")
def generate_resume(job_id: int, bg: BackgroundTasks):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT analysis_status FROM jobs WHERE id = %s;", (job_id,))
            job = cur.fetchone()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            cur.execute("SELECT input_doc_id FROM job_analysis WHERE job_id = %s;", (job_id,))
            analysis = cur.fetchone()
            if not analysis or not analysis["input_doc_id"]:
                raise HTTPException(status_code=400, detail="No analysis found — run /analyze first")

    bg.add_task(generate_resume_bg, job_id)
    return {"message": "generating"}
