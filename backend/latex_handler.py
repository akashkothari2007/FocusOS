from db import get_conn
import logging

log = logging.getLogger("latex_handler")


def fmt_profile(profile) -> str:
    """Render profile experiences + projects as plain text for prompt context."""
    if not profile:
        return ""
    lines = []
    for exp in profile.get("experiences") or []:
        role    = exp.get("role", "")
        company = exp.get("company", "")
        date    = exp.get("date", "")
        lines.append(f"Experience: {role} at {company} ({date})")
        for bullet in exp.get("bullets") or []:
            lines.append(f"  - {bullet}")
    for proj in profile.get("projects") or []:
        title = proj.get("title", "")
        desc  = proj.get("description", "")
        tech  = proj.get("tech", "")
        lines.append(f"Project: {title}" + (f" [{tech}]" if tech else ""))
        if desc:
            lines.append(f"  {desc}")
    return "\n".join(lines)


def extract_experiences_and_projects(input_doc_id: int) -> str:
    """Extract experiences and projects from LaTeX."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT content FROM docs WHERE id = %s;", (input_doc_id,))
            doc = cur.fetchone()
    print(doc)
    return doc

if __name__ == "__main__":
    extract_experiences_and_projects(4)