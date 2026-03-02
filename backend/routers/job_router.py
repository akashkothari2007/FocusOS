import json
import os
from urllib.parse import urlparse, parse_qs
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional, Literal
from openai import AzureOpenAI
from db import get_conn
from models.job_models import CreateJob, UpdateJob, AnalyzeJob

router = APIRouter(prefix="/api/v1")

# ---------------------------------------------------------------------------
# Azure OpenAI — lazy singleton so env vars are read at call time, not import
# ---------------------------------------------------------------------------

_az_client = None

def _get_az() -> AzureOpenAI:
    global _az_client
    if _az_client is None:
        # AZURE_FOUNDRY_ENDPOINT is the full deployment URL, e.g.:
        #   https://<resource>.cognitiveservices.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01-preview
        # AzureOpenAI client needs only the base URL + api_version separately.
        full_url = os.environ["AZURE_FOUNDRY_ENDPOINT"]
        parsed = urlparse(full_url)
        base_endpoint = f"{parsed.scheme}://{parsed.netloc}"
        api_version = parse_qs(parsed.query).get("api-version", ["2025-01-01-preview"])[0]
        _az_client = AzureOpenAI(
            azure_endpoint=base_endpoint,
            api_key=os.environ["AZURE_FOUNDRY_API_KEY"],
            api_version=api_version,
        )
    return _az_client

MODEL = "gpt-4o"

# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

def _retry(fn, retries: int = 2):
    """Call fn(), retrying up to `retries` additional times on any exception."""
    exc = None
    for _ in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            exc = e
    raise exc

# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

def generate_summary(job_id: int, description: str) -> None:
    """Summarize a job description and patch jobs.summary + analysis_status."""
    def _call():
        resp = _get_az().chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a job description analyst. "
                        "Always respond with valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Summarize the following job description in 3-4 concise bullet points "
                        "as plain text (no markdown formatting).\n\n"
                        f"Job Description:\n{description}\n\n"
                        'Return JSON: {"summary": "<bullet points separated by newlines>"}'
                    ),
                },
            ],
        )
        return json.loads(resp.choices[0].message.content)["summary"]

    try:
        summary = _retry(_call)
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

    # Fetch required data — own connection per spec
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT description, summary FROM jobs WHERE id = %s;", (job_id,)
            )
            job = cur.fetchone()
            cur.execute("SELECT content FROM docs WHERE id = %s;", (input_doc_id,))
            doc = cur.fetchone()

    if not job or not doc:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'error' WHERE id = %s;", (job_id,)
                )
        return

    # --- Step 1: match_score + keywords ---
    def _step1():
        resp = _get_az().chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert resume and job description analyzer. "
                        "Always respond with valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Job Description:\n{job['description'] or ''}\n\n"
                        f"Resume (LaTeX source):\n{doc['content']}\n\n"
                        "Score how well this resume matches the job and extract the key "
                        "technical skills and requirements from the job description.\n"
                        'Return JSON: {"match_score": <integer 0-100>, "keywords": [<string>, ...]}'
                    ),
                },
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        return int(data["match_score"]), list(data["keywords"])

    try:
        match_score, keywords = _retry(_step1)
    except Exception:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET analysis_status = 'error' WHERE id = %s;", (job_id,)
                )
        return  # Abort: step 1 is required

    # Surface step-1 results immediately so frontend can show them
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
    def _step2():
        resp = _get_az().chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert resume coach. "
                        "Always respond with valid JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Key job requirements / keywords: {', '.join(keywords)}\n\n"
                        f"Resume (LaTeX source):\n{doc['content']}\n\n"
                        f"Job Description:\n{job['description'] or ''}\n\n"
                        "Provide specific, actionable suggestions to better tailor this resume "
                        "to the listed job keywords. Each suggestion should reference a concrete "
                        "change the candidate can make.\n"
                        'Return JSON: {"suggestions": [<string>, ...]}'
                    ),
                },
            ],
        )
        return list(json.loads(resp.choices[0].message.content)["suggestions"])

    suggestions = []
    try:
        suggestions = _retry(_step2)
    except Exception:
        pass  # Step 2 failure is non-fatal — leave suggestions as []

    # Patch step-2 results and mark done (same connection = one commit)
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
    # Pre-set analysis_status so the returned row accurately reflects imminent bg work
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

            # Stub row returned immediately; run_analysis fills in real values
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


@router.post("/jobs/{job_id}/generate-resume")
def generate_resume(job_id: int):
    return {"message": "not implemented yet"}
