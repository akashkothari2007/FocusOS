"""Inject AI-generated bullet changes back into a LaTeX resume without AI touching LaTeX."""

import re
import logging

log = logging.getLogger("resume_injector")


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters in plain-text content."""
    text = text.replace("%", r"\%")
    text = text.replace("#", r"\#")
    text = text.replace("&", r"\&")
    return text


def _build_item_list(bullets: list[str]) -> str:
    items = "\n".join(f"          \\resumeItem{{{_escape_latex(b)}}}" for b in bullets)
    return f"        \\resumeItemListStart\n{items}\n        \\resumeItemListEnd"


def _find_item_list_span(latex: str, after: int) -> tuple[int, int] | None:
    """Return (start, end) of the next \\resumeItemListStart...\\resumeItemListEnd after `after`."""
    s = latex.find(r"\resumeItemListStart", after)
    if s == -1:
        return None
    e = latex.find(r"\resumeItemListEnd", s)
    if e == -1:
        return None
    return s, e + len(r"\resumeItemListEnd")


def _replace_bullets_for_experience(latex: str, role: str, company: str, new_bullets: list[str]) -> str:
    pattern = re.compile(
        r"\\resumeSubheading\s*\{" + re.escape(role) + r"\}\{[^}]*\}\s*\{" + re.escape(company) + r"\}",
        re.DOTALL,
    )
    m = pattern.search(latex)
    if not m:
        log.warning(f"  inject: could not find experience '{role} @ {company}'")
        return latex
    span = _find_item_list_span(latex, m.end())
    if not span:
        log.warning(f"  inject: no item list found after experience '{role} @ {company}'")
        return latex
    return latex[: span[0]] + _build_item_list(new_bullets) + latex[span[1] :]


def _swap_experience(
    latex: str,
    remove_role: str, remove_company: str,
    add_role: str, add_company: str,
    add_date: str, add_location: str,
    new_bullets: list[str],
) -> str:
    """Replace one \\resumeSubheading + bullets with a new experience."""
    pattern = re.compile(
        r"\\resumeSubheading\s*\{" + re.escape(remove_role) + r"\}\{[^}]*\}\s*\{" + re.escape(remove_company) + r"\}",
        re.DOTALL,
    )
    m = pattern.search(latex)
    if not m:
        log.warning(f"  inject: could not find experience to swap '{remove_role} @ {remove_company}'")
        return latex
    span = _find_item_list_span(latex, m.start())
    if not span:
        log.warning(f"  inject: no item list for experience swap '{remove_role} @ {remove_company}'")
        return latex
    new_heading = (
        "\\resumeSubheading\n"
        f"      {{{_escape_latex(add_role)}}}{{{_escape_latex(add_date)}}}\n"
        f"      {{{_escape_latex(add_company)}}}{{{_escape_latex(add_location)}}}"
    )
    new_block = new_heading + "\n" + _build_item_list(new_bullets)
    return latex[: m.start()] + new_block + latex[span[1] :]


def _replace_bullets_for_project(latex: str, title: str, new_bullets: list[str]) -> str:
    proj_re = re.compile(r"\\resumeProjectHeading\s*\{")
    for m in proj_re.finditer(latex):
        i = m.end()
        depth, j = 1, i
        while j < len(latex) and depth > 0:
            if latex[j] == "{":
                depth += 1
            elif latex[j] == "}":
                depth -= 1
            j += 1
        arg1 = latex[i : j - 1]
        if title.lower() in arg1.lower():
            span = _find_item_list_span(latex, m.start())
            if span:
                return latex[: span[0]] + _build_item_list(new_bullets) + latex[span[1] :]
    log.warning(f"  inject: could not find project '{title}'")
    return latex


def _swap_project(
    latex: str, remove_title: str, add_title: str, add_tech: str, new_bullets: list[str]
) -> str:
    proj_re = re.compile(r"\\resumeProjectHeading\s*\{")
    for m in proj_re.finditer(latex):
        i = m.end()
        depth, j = 1, i
        while j < len(latex) and depth > 0:
            if latex[j] == "{":
                depth += 1
            elif latex[j] == "}":
                depth -= 1
            j += 1
        arg1 = latex[i : j - 1]
        if remove_title.lower() in arg1.lower():
            span = _find_item_list_span(latex, m.start())
            if not span:
                log.warning(f"  inject: no item list for swap remove='{remove_title}'")
                return latex
            if add_tech:
                heading_content = (
                    f"\\textbf{{{_escape_latex(add_title)}}} $|$ \\emph{{{_escape_latex(add_tech)}}}"
                )
            else:
                heading_content = f"\\textbf{{{_escape_latex(add_title)}}}"
            new_heading = "\\resumeProjectHeading\n      {" + heading_content + "}{}"
            new_block = new_heading + "\n" + _build_item_list(new_bullets)
            return latex[: m.start()] + new_block + latex[span[1] :]
    log.warning(f"  inject: could not find project to swap: '{remove_title}'")
    return latex


def inject_changes(
    base_latex: str,
    ai_output: dict,
    project_plan: list[dict],
    experience_plan: list[dict] | None = None,
) -> str:
    """Inject AI-generated bullet rewrites into base LaTeX. AI never touches LaTeX syntax.

    ai_output: {"experiences": [{role, company, bullets}], "projects": [{title, tech, bullets}]}
    project_plan:    [{"action": "keep"|"swap", "title"|"remove"/"add", ...}]
    experience_plan: [{"action": "keep"|"swap", "role"/"company" or "remove_role"/"add_role", ...}]
    """
    latex = base_latex
    experience_plan = experience_plan or []

    # --- Experiences ---
    ai_experiences = {(e["role"], e["company"]): e for e in ai_output.get("experiences", [])}

    if experience_plan:
        for plan_item in experience_plan:
            action = plan_item.get("action", "keep")
            if action == "keep":
                role = plan_item.get("role", "")
                company = plan_item.get("company", "")
                exp = ai_experiences.get((role, company))
                if exp and exp.get("bullets"):
                    log.info(f"  inject exp : KEEP '{role} @ {company}'  ({len(exp['bullets'])} bullets)")
                    latex = _replace_bullets_for_experience(latex, role, company, exp["bullets"])
            elif action == "swap":
                remove_role = plan_item.get("remove_role", "")
                remove_company = plan_item.get("remove_company", "")
                add_role = plan_item.get("add_role", "")
                add_company = plan_item.get("add_company", "")
                add_date = plan_item.get("add_date", "")
                add_location = plan_item.get("add_location", "")
                exp = ai_experiences.get((add_role, add_company))
                if exp and exp.get("bullets"):
                    log.info(f"  inject exp : SWAP '{remove_role}' → '{add_role}'  ({len(exp['bullets'])} bullets)")
                    latex = _swap_experience(
                        latex, remove_role, remove_company,
                        add_role, add_company, add_date, add_location,
                        exp["bullets"],
                    )
    else:
        # Backward compat: no plan — just replace all experience bullets
        for exp in ai_output.get("experiences", []):
            role = exp.get("role", "")
            company = exp.get("company", "")
            bullets = exp.get("bullets", [])
            if role and company and bullets:
                log.info(f"  inject exp : '{role} @ {company}'  ({len(bullets)} bullets)")
                latex = _replace_bullets_for_experience(latex, role, company, bullets)

    # --- Projects ---
    ai_projects = {p["title"]: p for p in ai_output.get("projects", [])}

    for plan_item in project_plan:
        action = plan_item.get("action", "keep")
        if action == "keep":
            title = plan_item.get("title", "")
            if title in ai_projects:
                bullets = ai_projects[title].get("bullets", [])
                log.info(f"  inject proj: KEEP '{title}'  ({len(bullets)} bullets)")
                latex = _replace_bullets_for_project(latex, title, bullets)
        elif action == "swap":
            remove_title = plan_item.get("remove", "")
            add_title = plan_item.get("add", "")
            if add_title in ai_projects:
                bullets = ai_projects[add_title].get("bullets", [])
                tech = ai_projects[add_title].get("tech", "")
                log.info(f"  inject proj: SWAP '{remove_title}' → '{add_title}'  ({len(bullets)} bullets)")
                latex = _swap_project(latex, remove_title, add_title, tech, bullets)

    return latex
