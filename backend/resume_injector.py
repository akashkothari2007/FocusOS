"""Inject AI-generated bullet changes back into a LaTeX resume without AI touching LaTeX."""

import re
import logging

log = logging.getLogger("resume_injector")


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters in plain-text bullet content."""
    text = text.replace("%", r"\%")
    text = text.replace("#", r"\#")
    text = text.replace("&", r"\&")
    return text


def _build_item_list(bullets: list[str]) -> str:
    items = "\n".join(f"          \\resumeItem{{{_escape_latex(b)}}}" for b in bullets)
    return f"        \\resumeItemListStart\n{items}\n        \\resumeItemListEnd"


def _find_item_list_span(latex: str, after: int) -> tuple[int, int] | None:
    """Return (start, end) of the next \\resumeItemListStart...\\resumeItemListEnd after `after`."""
    start_marker = r"\resumeItemListStart"
    end_marker = r"\resumeItemListEnd"
    s = latex.find(start_marker, after)
    if s == -1:
        return None
    e = latex.find(end_marker, s)
    if e == -1:
        return None
    return s, e + len(end_marker)


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
                heading_content = f"\\textbf{{{add_title}}} $|$ \\emph{{{add_tech}}}"
            else:
                heading_content = f"\\textbf{{{add_title}}}"
            new_heading = f"\\resumeProjectHeading{{{{{heading_content}}}}}{{}}"
            # \resumeProjectHeading takes {{first_arg}}{second_arg}
            # Build it correctly:
            new_heading = "\\resumeProjectHeading\n      {" + heading_content + "}{}"
            new_block = new_heading + "\n" + _build_item_list(new_bullets)
            return latex[: m.start()] + new_block + latex[span[1] :]
    log.warning(f"  inject: could not find project to swap: '{remove_title}'")
    return latex


def inject_changes(base_latex: str, ai_output: dict, project_plan: list[dict]) -> str:
    """Inject AI-generated bullet rewrites into base LaTeX. AI never touches LaTeX syntax.

    ai_output: {"experiences": [{role, company, bullets}], "projects": [{title, tech, bullets}]}
    project_plan: [{"action": "keep"|"swap", "title": ..., "remove": ..., "add": ..., ...}]
    """
    latex = base_latex

    for exp in ai_output.get("experiences", []):
        role = exp.get("role", "")
        company = exp.get("company", "")
        bullets = exp.get("bullets", [])
        if role and company and bullets:
            log.info(f"  inject exp : {role} @ {company}  ({len(bullets)} bullets)")
            latex = _replace_bullets_for_experience(latex, role, company, bullets)

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
