"""Prompt templates for AI calls."""

import json


def summary_messages(description: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": "You are a job description analyst and ATS scanner. Always respond with valid JSON only.",
        },
        {
            "role": "user",
            "content": (
                "Summarize this job description in exactly 4-6 bullet points. "
                "Be specific: name the tech stack, seniority level, the 2-3 most important responsibilities, "
                "and must-have qualifications and requirements. "
                "After, read the job description as an ATS system and extract the top 12-15 ATS keywords. "
                "ONLY include: programming languages, frameworks, technical skills, methodologies, and domain terms. "
                "EXCLUDE: salary, benefits, perks, work arrangements, company culture, soft skills like 'collaboration', and anything non-technical. "
                "Plain text only, no markdown.\n\n"
                f"Job Description:\n{description}\n\n"
                'Return JSON: {"summary": "<bullets separated by newlines>", "keywords": [<string>, ...]}'
            ),
        },
    ]


def _fmt_parsed_experiences(parsed: dict) -> str:
    lines = []
    for exp in parsed.get("experiences", []):
        lines.append(f"- {exp.role} at {exp.company} ({exp.date})")
        for b in exp.bullets:
            lines.append(f"  • {b}")
    return "\n".join(lines)


def _fmt_parsed_projects(parsed: dict) -> str:
    lines = []
    for proj in parsed.get("projects", []):
        tech_str = f" | {proj.tech}" if proj.tech else ""
        lines.append(f"- {proj.title}{tech_str}")
        for b in proj.bullets:
            lines.append(f"  • {b}")
    return "\n".join(lines)


def analysis_messages(
    keywords: list[str],
    job_summary: str,
    parsed: dict,
    profile_ctx: str,
    n_projects: int,
    n_experiences: int,
) -> list[dict]:
    exp_block = _fmt_parsed_experiences(parsed)
    proj_block = _fmt_parsed_projects(parsed)
    profile_block = (
        f"\nProfile items (not on resume — available for swap):\n{profile_ctx}\n"
        if profile_ctx
        else ""
    )

    schema = json.dumps(
        {
            "match_score": 72,
            "overall": "One-line match summary.",
            "experience_plan": [
                {"action": "keep", "role": "...", "company": "...", "notes": ["specific bullet-level note"]},
                {
                    "action": "swap",
                    "remove_role": "...", "remove_company": "...",
                    "add_role": "...", "add_company": "...",
                    "notes": ["why this swap improves fit"],
                },
            ],
            "project_plan": [
                {"action": "keep", "title": "ProjectA", "notes": ["emphasis note"]},
                {"action": "swap", "remove": "ProjectB", "add": "ProfileProject", "notes": ["why swap"]},
            ],
        },
        indent=2,
    )

    return [
        {
            "role": "system",
            "content": (
                "You are a strict ATS system and honest resume coach. "
                "Score calibration: 0-30 = weak, 31-55 = partial, 56-75 = decent, 76-90 = strong, 91-100 = near-perfect. "
                "Most candidates score 35-65. Do not inflate. "
                "Penalise clearly missing hard requirements. "
                "Never invent experience — if something is missing, say so plainly. "
                "Always respond with valid JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Job Summary:\n{job_summary}\n\n"
                f"ATS Keywords: {', '.join(keywords)}\n\n"
                f"Resume Experiences:\n{exp_block}\n\n"
                f"Resume Projects (currently on resume):\n{proj_block}\n"
                + profile_block
                + "\nTasks:\n"
                "1. Score how well this candidate matches the job RIGHT NOW.\n"
                f"2. Decide the experience_plan: exactly {n_experiences} entries (one per slot). "
                "DEFAULT is KEEP with specific bullet-level rewrite notes. "
                "SWAP is rarely correct — only if the profile experience is a substantially stronger match AND "
                "the existing experience is clearly weak for this role. "
                "NEVER swap for: soft skills, 'diversity', consulting exposure, or keyword overlap alone. "
                "NEVER swap a technical/software engineering role for a hardware, embedded, or non-software role. "
                "Strong recent software internships should almost always be kept.\n"
                f"3. Decide the project_plan: exactly {n_projects} entries (one per slot). "
                "DEFAULT is KEEP. Only swap if a profile project is directly and obviously more relevant. "
                "Do NOT swap to 'add diversity' or for vague alignment reasons.\n\n"
                "For KEEP entries: notes should say what specific bullets to strengthen and what angle to take. "
                "The goal is great bullet rewrites — swaps are a last resort.\n\n"
                "4. For each KEEP entry: suggest specific, truthful rewrites that naturally incorporate relevant ATS keywords. "
                "Only suggest adding a keyword if there is a concrete, genuine way to work it in — never suggest forcing a keyword "
                "that does not fit the actual work done. A missing keyword is better than a forced one.\n"
                f"Return JSON matching this schema exactly:\n{schema}"
            ),
        },
    ]


def resume_messages(
    keywords: list[str],
    parsed: dict,
    suggestions: dict,
    new_profile_projects: list,
    new_profile_experiences: list | None = None,
) -> list[dict]:
    """Build prompt for bullet rewrite. No LaTeX in, no LaTeX out."""
    experience_plan = suggestions.get("experience_plan", [])
    project_plan = suggestions.get("project_plan", [])

    existing_exp_lookup = {(e.role, e.company): e for e in parsed.get("experiences", [])}
    existing_proj_lookup = {p.title: p for p in parsed.get("projects", [])}
    profile_proj_lookup = {p.get("title", ""): p for p in new_profile_projects}
    profile_exp_lookup = {e.get("role", "").lower(): e for e in (new_profile_experiences or [])}

    # Build experience blocks
    exp_blocks = []
    if experience_plan:
        for plan_item in experience_plan:
            action = plan_item.get("action", "keep")
            notes = plan_item.get("notes", [])
            notes_str = ("\n  Notes: " + "; ".join(notes)) if notes else ""

            if action == "keep":
                role = plan_item.get("role", "")
                company = plan_item.get("company", "")
                exp = existing_exp_lookup.get((role, company))
                if not exp:
                    continue
                max_chars = int(max((len(b) for b in exp.bullets), default=120) * 0.9)
                bullets_str = "\n".join(f"  [{i+1}] ({len(b)}ch) {b}" for i, b in enumerate(exp.bullets))
                exp_blocks.append(
                    f"- KEEP {role} at {company}\n"
                    f"  Bullet count: {len(exp.bullets)} | Max chars per bullet: {max_chars}\n"
                    f"  Current bullets:\n{bullets_str}"
                    + notes_str
                )
            elif action == "swap":
                remove_role = plan_item.get("remove_role", "")
                remove_company = plan_item.get("remove_company", "")
                add_role = plan_item.get("add_role", "")
                add_company = plan_item.get("add_company", "")
                old_exp = existing_exp_lookup.get((remove_role, remove_company))
                bullet_count = len(old_exp.bullets) if old_exp else 3
                max_chars = int(max((len(b) for b in old_exp.bullets), default=120) * 0.9) if old_exp else 110
                new_exp = profile_exp_lookup.get(add_role.lower(), {})
                desc_parts = []
                if new_exp.get("bullets"):
                    desc_parts.append("Profile bullets: " + " | ".join(new_exp["bullets"]))
                elif new_exp.get("description"):
                    desc_parts.append("Description: " + new_exp["description"])
                desc_str = ("\n  " + "\n  ".join(desc_parts)) if desc_parts else ""
                exp_blocks.append(
                    f"- SWAP: replace '{remove_role} at {remove_company}' with '{add_role} at {add_company}'\n"
                    f"  Bullet count: {bullet_count} | Max chars per bullet: {max_chars}"
                    + desc_str
                    + notes_str
                )
    else:
        # Backward compat: experience_notes (old format) or plain keep-all
        experience_notes = {
            (en["role"], en["company"]): en.get("notes", [])
            for en in suggestions.get("experience_notes", [])
        }
        for exp in parsed.get("experiences", []):
            notes = experience_notes.get((exp.role, exp.company), [])
            notes_str = ("\n  Notes: " + "; ".join(notes)) if notes else ""
            max_chars = int(max((len(b) for b in exp.bullets), default=120) * 0.9)
            bullets_str = "\n".join(f"  [{i+1}] ({len(b)}ch) {b}" for i, b in enumerate(exp.bullets))
            exp_blocks.append(
                f"- {exp.role} at {exp.company}\n"
                f"  Bullet count: {len(exp.bullets)} | Max chars per bullet: {max_chars}\n"
                f"  Current bullets:\n{bullets_str}"
                + notes_str
            )

    # Build project blocks
    proj_blocks = []
    for plan_item in project_plan:
        action = plan_item.get("action", "keep")
        notes = plan_item.get("notes", [])
        notes_str = ("\n  Notes: " + "; ".join(notes)) if notes else ""

        if action == "keep":
            title = plan_item.get("title", "")
            proj = existing_proj_lookup.get(title)
            if not proj:
                continue
            tech_str = f" | {proj.tech}" if proj.tech else ""
            max_chars = int(max((len(b) for b in proj.bullets), default=120) * 0.9)
            bullets_str = "\n".join(f"  [{i+1}] ({len(b)}ch) {b}" for i, b in enumerate(proj.bullets))
            proj_blocks.append(
                f"- KEEP {title}{tech_str}\n"
                f"  Bullet count: {len(proj.bullets)} | Max chars per bullet: {max_chars}\n"
                f"  Current bullets:\n{bullets_str}"
                + notes_str
            )

        elif action == "swap":
            remove = plan_item.get("remove", "")
            add = plan_item.get("add", "")
            old_proj = existing_proj_lookup.get(remove)
            bullet_count = len(old_proj.bullets) if old_proj else 3
            max_chars = int(max((len(b) for b in old_proj.bullets), default=120) * 0.9) if old_proj else 110
            new_proj = profile_proj_lookup.get(add, {})
            tech = new_proj.get("tech", "")
            desc_parts = []
            if new_proj.get("bullets"):
                desc_parts.append("Profile bullets: " + " | ".join(new_proj["bullets"]))
            elif new_proj.get("description"):
                desc_parts.append("Description: " + new_proj["description"])
            desc_str = ("\n  " + "\n  ".join(desc_parts)) if desc_parts else ""
            proj_blocks.append(
                f"- SWAP: replace '{remove}' with '{add}'"
                + (f" | {tech}" if tech else "")
                + f"\n  Bullet count: {bullet_count} | Max chars per bullet: {max_chars}"
                + desc_str
                + notes_str
            )

    schema = json.dumps(
        {
            "experiences": [{"role": "...", "company": "...", "bullets": ["...", "...", "..."]}],
            "projects": [{"title": "...", "tech": "...", "bullets": ["...", "...", "..."]}],
        },
        indent=2,
    )

    return [
        {
            "role": "system",
            "content": (
                "You are an expert resume writer. "
                "EVERY bullet must be rewritten with stronger, more targeted phrasing — never return a bullet verbatim. "
                "Bold 1-3 high-impact terms per bullet. "
                "IMPORTANT: this output is JSON, so backslashes must be doubled — write \\\\textbf{term} not \\textbf{term}. "
                "Example: 'Deployed \\\\textbf{Kubernetes} orchestration serving \\\\textbf{50k+} daily requests'. "
                "Bold specific tech, metrics, and key outcomes only. Never bold generic words. "
                "Weave in job keywords only where they fit naturally and truthfully — if a keyword does not genuinely apply "
                "to the work described, omit it entirely. A missing keyword reads far better than a forced one. "
                "Preserve truthfulness — never fabricate experience. "
                "EXACT original bullet count per section. "
                "Each bullet MUST stay under its Max chars (one-page hard limit). "
                "Always respond with valid JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Job Keywords to weave in naturally: {', '.join(keywords)}\n\n"
                "Experiences — rewrite bullets:\n"
                + "\n\n".join(exp_blocks)
                + "\n\nProjects — keep or replace:\n"
                + "\n\n".join(proj_blocks)
                + "\n\nRules:\n"
                "1. EXACT bullet count — never add or remove\n"
                "2. HARD LIMIT: stay under Max chars per bullet\n"
                "3. Action-verb first, quantify where genuine data exists\n"
                "4. For SWAP entries, write fresh bullets from the profile description\n"
                "5. Output experiences in plan order; output projects in plan order\n\n"
                f"Return JSON:\n{schema}"
            ),
        },
    ]
