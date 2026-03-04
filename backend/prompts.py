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
) -> list[dict]:
    exp_block = _fmt_parsed_experiences(parsed)
    proj_block = _fmt_parsed_projects(parsed)
    profile_block = (
        f"\nProfile Projects (not on resume — available for swap):\n{profile_ctx}\n"
        if profile_ctx
        else ""
    )

    schema = json.dumps(
        {
            "match_score": 72,
            "overall": "One-line match summary.",
            "experience_notes": [
                {"role": "...", "company": "...", "notes": ["specific bullet-level note", "..."]}
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
                "2. For each experience, give specific bullet-level notes on what to reframe or emphasize. "
                "Reference the exact bullet content, not just the role.\n"
                f"3. Decide the project_plan: select exactly {n_projects} project slots. "
                "For each slot: 'keep' an existing project or 'swap' one out for a better-fit profile project. "
                "If no swap improves fit, keep all. "
                "If a hard requirement is missing, note it plainly — never fabricate.\n\n"
                f"Return JSON matching this schema exactly:\n{schema}"
            ),
        },
    ]


def resume_messages(
    keywords: list[str],
    parsed: dict,
    suggestions: dict,
    new_profile_projects: list,
) -> list[dict]:
    """Build prompt for bullet rewrite. No LaTeX in, no LaTeX out."""
    experience_notes = {
        (en["role"], en["company"]): en.get("notes", [])
        for en in suggestions.get("experience_notes", [])
    }
    project_plan = suggestions.get("project_plan", [])

    existing_proj_lookup = {p.title: p for p in parsed.get("projects", [])}
    profile_proj_lookup = {p.get("title", ""): p for p in new_profile_projects}

    # Build experience blocks with exact bullet count + max char limit
    exp_blocks = []
    for exp in parsed.get("experiences", []):
        notes = experience_notes.get((exp.role, exp.company), [])
        notes_str = ("\n  Notes: " + "; ".join(notes)) if notes else ""
        max_chars = max((len(b) for b in exp.bullets), default=120)
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
            max_chars = max((len(b) for b in proj.bullets), default=120)
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
            max_chars = max((len(b) for b in old_proj.bullets), default=120) if old_proj else 120
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
                "Rewrite bullet points to incorporate the given keywords and notes. "
                "Preserve truthfulness — never fabricate experience. "
                "Match the EXACT original bullet count per section. "
                "Each bullet MUST stay under its specified Max chars — this is a one-page hard limit. "
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
                "1. EXACT bullet count per section — never add or remove bullets\n"
                "2. HARD LIMIT: each bullet must be UNDER its Max chars value — exceeding it causes layout overflow and breaks the one-page resume\n"
                "3. Action-verb first, quantify where genuine data exists\n"
                "4. For SWAP projects, write fresh bullets from the profile description\n"
                "5. Output experiences in input order; output projects in plan order using final title\n\n"
                f"Return JSON:\n{schema}"
            ),
        },
    ]
