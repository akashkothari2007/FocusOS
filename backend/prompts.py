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
                f"2. Decide the experience_plan: exactly {n_experiences} entries (one per experience slot). "
                "Default action is KEEP with bullet-level rewrite notes. "
                "Only recommend SWAP if the profile experience is CLEARLY more relevant to this specific job "
                "AND the existing experience being removed is a genuine downgrade for this role. "
                "NEVER swap a strong software engineering experience for a hardware/embedded/unrelated role just because it shares a keyword. "
                "Keyword overlap alone is not a reason to swap — overall relevance and strength matter.\n"
                f"3. Decide the project_plan: exactly {n_projects} entries (one per project slot). "
                "Default is KEEP with emphasis notes. "
                "Only recommend SWAP if a profile project significantly outperforms the existing one for this job. "
                "Never fabricate — if a hard requirement is missing, note it plainly.\n\n"
                "If in doubt on any swap: KEEP. The resume is already good — the goal is targeted bullet rewrites, not wholesale replacement.\n\n"
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
                "2. HARD LIMIT: each bullet must be UNDER its Max chars — exceeding causes layout overflow\n"
                "3. Action-verb first, quantify where genuine data exists\n"
                "4. For SWAP entries, write fresh bullets from the profile description\n"
                "5. Output experiences in plan order (use add_role/add_company for swapped-in entries)\n"
                "6. Output projects in plan order using final title\n\n"
                f"Return JSON:\n{schema}"
            ),
        },
    ]
