import json
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Optional, Literal

from db import get_conn
from models.job_models import CreateJob, UpdateJob, AnalyzeJob, GenerateResumeBody
from ai import chat_json
from jobs.latex_handler import parse_latex
from prompts import summary_messages, analysis_messages, resume_messages
from jobs.resume_injector import inject_changes  

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

    # Pass profile items NOT already on the resume (both projects and experiences)
    resume_titles = {p.title for p in parsed["projects"]}
    resume_exp_keys = {(e.role.lower(), e.company.lower()) for e in parsed["experiences"]}
    extra_projs = [p for p in (profile.get("projects") or []) if p.get("title") not in resume_titles]
    extra_exps = [
        e for e in (profile.get("experiences") or [])
        if (e.get("role", "").lower(), e.get("company", "").lower()) not in resume_exp_keys
    ]
    log.info(f"  Extra for analysis: {len(extra_projs)} projects, {len(extra_exps)} experiences")

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
            extra_experiences=extra_exps,
            extra_projects=extra_projs,
            n_projects=len(parsed["projects"]),
            n_experiences=len(parsed["experiences"]),
        ))
        match_score = int(data["match_score"])
        suggestions = {k: v for k, v in data.items() if k != "match_score"}
        log.info(f"  Match score  : {match_score}/100")
        log.info(f"  experiences  : {len(suggestions.get('experiences', []))}")
        log.info(f"  projects     : {len(suggestions.get('projects', []))}")
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

def generate_resume_bg(job_id: int, plan_overrides: dict | None = None) -> None:
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
            log.info("  [compat] old flat suggestions — keep-all plan, no notes")
            project_plan = [{"action": "keep", "title": p.title, "notes": []} for p in parsed["projects"]]
            suggestions_dict = {"experience_plan": [], "project_plan": project_plan}
            new_profile_projects = []
            new_profile_experiences = []
            experience_plan = []

        elif "experiences" in suggestions_raw or "projects" in suggestions_raw:
            # New format: flat experiences/projects arrays with recommended/notes
            suggestions_dict = suggestions_raw
            all_exp_items = suggestions_dict.get("experiences", [])
            all_proj_items = suggestions_dict.get("projects", [])
            resume_exp_keys = {(e.role.lower(), e.company.lower()) for e in parsed["experiences"]}
            resume_proj_keys = {p.title.lower() for p in parsed["projects"]}

            # Determine selections (user overrides or AI defaults)
            if plan_overrides and plan_overrides.get("selected_experiences") is not None:
                sel_exp_keys = {(e["role"].lower(), e["company"].lower()) for e in plan_overrides["selected_experiences"]}
            else:
                sel_exp_keys = {(e["role"].lower(), e["company"].lower()) for e in all_exp_items if e.get("recommended")}

            if plan_overrides and plan_overrides.get("selected_projects") is not None:
                sel_proj_keys = {p["title"].lower() for p in plan_overrides["selected_projects"]}
            else:
                sel_proj_keys = {p["title"].lower() for p in all_proj_items if p.get("recommended")}

            # Notes and profile lookups
            exp_notes_lookup = {(e["role"].lower(), e["company"].lower()): e.get("notes", "") for e in all_exp_items}
            proj_notes_lookup = {p["title"].lower(): p.get("notes", "") for p in all_proj_items}
            prof_exp_lookup = {e.get("role", "").lower(): e for e in (profile.get("experiences") or [])}
            prof_proj_lookup_full = {p.get("title", "").lower(): p for p in (profile.get("projects") or [])}

            # Selected profile items not currently on resume
            selected_profile_exps = [
                e for e in all_exp_items
                if (e["role"].lower(), e["company"].lower()) not in resume_exp_keys
                and (e["role"].lower(), e["company"].lower()) in sel_exp_keys
            ]
            selected_profile_projs = [
                p for p in all_proj_items
                if p["title"].lower() not in resume_proj_keys and p["title"].lower() in sel_proj_keys
            ]

            # Build experience_plan — one entry per original resume slot
            profile_exp_subs = list(selected_profile_exps)
            experience_plan = []
            for resume_exp in parsed["experiences"]:
                key = (resume_exp.role.lower(), resume_exp.company.lower())
                notes_str = exp_notes_lookup.get(key, "")
                if key in sel_exp_keys:
                    experience_plan.append({
                        "action": "keep",
                        "role": resume_exp.role,
                        "company": resume_exp.company,
                        "notes": [notes_str] if notes_str else [],
                    })
                elif profile_exp_subs:
                    sub = profile_exp_subs.pop(0)
                    sub_key = (sub["role"].lower(), sub["company"].lower())
                    sub_notes = exp_notes_lookup.get(sub_key, "")
                    prof_exp = prof_exp_lookup.get(sub["role"].lower(), {})
                    experience_plan.append({
                        "action": "swap",
                        "remove_role": resume_exp.role,
                        "remove_company": resume_exp.company,
                        "add_role": sub["role"],
                        "add_company": sub["company"],
                        "add_date": prof_exp.get("date", ""),
                        "add_location": prof_exp.get("location", ""),
                        "notes": [sub_notes] if sub_notes else [],
                    })
                else:
                    experience_plan.append({
                        "action": "keep",
                        "role": resume_exp.role,
                        "company": resume_exp.company,
                        "notes": [notes_str] if notes_str else [],
                    })

            # Build project_plan — one entry per original resume slot
            profile_proj_subs = list(selected_profile_projs)
            project_plan = []
            for resume_proj in parsed["projects"]:
                pkey = resume_proj.title.lower()
                notes_str = proj_notes_lookup.get(pkey, "")
                if pkey in sel_proj_keys:
                    project_plan.append({
                        "action": "keep",
                        "title": resume_proj.title,
                        "notes": [notes_str] if notes_str else [],
                    })
                elif profile_proj_subs:
                    sub = profile_proj_subs.pop(0)
                    sub_pkey = sub["title"].lower()
                    sub_notes = proj_notes_lookup.get(sub_pkey, "")
                    prof_proj = prof_proj_lookup_full.get(sub_pkey, {})
                    link = prof_proj.get("link") or "https://github.com/akashkothari2007"
                    project_plan.append({
                        "action": "swap",
                        "remove": resume_proj.title,
                        "add": sub["title"],
                        "add_link": link,
                        "notes": [sub_notes] if sub_notes else [],
                    })
                else:
                    project_plan.append({
                        "action": "keep",
                        "title": resume_proj.title,
                        "notes": [notes_str] if notes_str else [],
                    })

            # Profile items context for resume_messages
            new_profile_experiences = [
                prof_exp_lookup[e["role"].lower()]
                for e in selected_profile_exps if e["role"].lower() in prof_exp_lookup
            ]
            new_profile_projects = [
                prof_proj_lookup_full[p["title"].lower()]
                for p in selected_profile_projs if p["title"].lower() in prof_proj_lookup_full
            ]

            # Merge derived plans into suggestions_dict for resume_messages
            suggestions_dict = {**suggestions_dict, "experience_plan": experience_plan, "project_plan": project_plan}

        else:
            # Old format: experience_plan/project_plan
            suggestions_dict = suggestions_raw
            project_plan = suggestions_dict.get("project_plan", [])
            experience_plan = suggestions_dict.get("experience_plan", [])

            # Profile items being swapped in
            swap_proj_titles = {s["add"].lower() for s in project_plan if s.get("action") == "swap"}
            new_profile_projects = [
                p for p in (profile.get("projects") or []) if p.get("title", "").lower() in swap_proj_titles
            ]
            swap_exp_roles = {s["add_role"].lower() for s in experience_plan if s.get("action") == "swap"}
            new_profile_experiences = [
                e for e in (profile.get("experiences") or []) if e.get("role", "").lower() in swap_exp_roles
            ]

            # Enrich experience_plan swap entries with date/location for inject_changes
            prof_exp_lookup = {e.get("role", "").lower(): e for e in (profile.get("experiences") or [])}
            for plan_item in experience_plan:
                if plan_item.get("action") == "swap":
                    prof_exp = prof_exp_lookup.get(plan_item.get("add_role", "").lower(), {})
                    plan_item.setdefault("add_date", prof_exp.get("date", ""))
                    plan_item.setdefault("add_location", prof_exp.get("location", ""))

            # Apply user plan overrides (old format: experience_plan/project_plan)
            if plan_overrides:
                if plan_overrides.get("project_plan") is not None:
                    project_plan = plan_overrides["project_plan"]
                    log.info("  [override] project_plan from frontend")
                if plan_overrides.get("experience_plan") is not None:
                    experience_plan = plan_overrides["experience_plan"]
                    log.info("  [override] experience_plan from frontend")

                # Re-enrich swap entries after override
                prof_exp_lookup = {e.get("role", "").lower(): e for e in (profile.get("experiences") or [])}
                for plan_item in experience_plan:
                    if plan_item.get("action") == "swap":
                        prof_exp = prof_exp_lookup.get(plan_item.get("add_role", "").lower(), {})
                        plan_item.setdefault("add_date", prof_exp.get("date", ""))
                        plan_item.setdefault("add_location", prof_exp.get("location", ""))

                # Recompute new_profile_* after overrides
                swap_proj_titles_eff = {s["add"].lower() for s in project_plan if s.get("action") == "swap"}
                new_profile_projects = [
                    p for p in (profile.get("projects") or []) if p.get("title", "").lower() in swap_proj_titles_eff
                ]
                swap_exp_roles_eff = {s["add_role"].lower() for s in experience_plan if s.get("action") == "swap"}
                new_profile_experiences = [
                    e for e in (profile.get("experiences") or []) if e.get("role", "").lower() in swap_exp_roles_eff
                ]

            # Enrich project swap entries with link
            prof_proj_lookup = {p.get("title", "").lower(): p for p in (profile.get("projects") or [])}
            for plan_item in project_plan:
                if plan_item.get("action") == "swap":
                    prof_proj = prof_proj_lookup.get(plan_item.get("add", "").lower(), {})
                    link = prof_proj.get("link") or "https://github.com/akashkothari2007"
                    plan_item.setdefault("add_link", link)

        proj_swaps = sum(1 for p in project_plan if p.get("action") == "swap")
        exp_swaps  = sum(1 for e in experience_plan if e.get("action") == "swap")
        log.info(f"  Keywords       : {len(keywords)}")
        log.info(f"  project_plan   : {len(project_plan)} entries  ({proj_swaps} swaps)")
        log.info(f"  experience_plan: {len(experience_plan)} entries  ({exp_swaps} swaps)")
        log.info("")
        log.info("  Calling AI for bullet rewrites (no LaTeX in/out)...")

        data = chat_json(
            resume_messages(
                keywords=keywords,
                parsed=parsed,
                suggestions=suggestions_dict,
                new_profile_projects=new_profile_projects,
                new_profile_experiences=new_profile_experiences,
            )
        )
        log.info(f"  AI output   : {len(data.get('experiences', []))} exp, {len(data.get('projects', []))} proj")

        log.info("  Injecting changes into base LaTeX...")
        latex = inject_changes(doc["content"], data, project_plan, experience_plan)
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
def generate_resume(job_id: int, bg: BackgroundTasks, body: GenerateResumeBody = GenerateResumeBody()):
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

    overrides = body.model_dump(exclude_none=True) or None
    bg.add_task(generate_resume_bg, job_id, overrides)
    return {"message": "generating"}
