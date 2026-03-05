from db import get_conn
import logging
import re
from dataclasses import dataclass, field


@dataclass
class Experience:
    role: str
    company: str
    date: str
    location: str
    bullets: list[str] = field(default_factory=list)

@dataclass
class Project:
    title: str
    tech: str
    link: str
    bullets: list[str] = field(default_factory=list)

@dataclass
class Skills:
    items: list[str] = field(default_factory=list)  # e.g. ["Languages: Python, C++, ...", ...]


log = logging.getLogger("latex_handler")

# simplify profile to plain text for prompt context
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
        title   = proj.get("title", "")
        tech    = proj.get("tech", "")
        bullets = proj.get("bullets") or []
        lines.append(f"Project: {title}" + (f" [{tech}]" if tech else ""))
        for bullet in bullets:
            lines.append(f"  - {bullet}")
    return "\n".join(lines)


# strip preamble from latex
def extract_latex_body(latex: str) -> str:
    """Strip preamble — only send content between begin/end document to save tokens."""
    match = re.search(r'\\begin\{document\}(.*?)\\end\{document\}', latex, re.DOTALL)
    return match.group(1).strip() if match else latex

# ---------------------------------------------------------------------------
# LaTeX parsing helpers
# ---------------------------------------------------------------------------

def _strip_latex(text: str) -> str:
    """Strip LaTeX formatting commands, returning plain readable text."""
    # Common character escapes first
    for esc, char in [('\\#', '#'), ('\\&', '&'), ('\\%', '%'), ('\\_', '_'), ('\\$', '$')]:
        text = text.replace(esc, char)
    # \href{url}{ → drop the url arg, keep the display content
    text = re.sub(r'\\href\{[^{}]*\}\{', '', text)
    # Drop all \command{ prefixes (textbf, emph, underline, small, textit, ...)
    text = re.sub(r'\\[a-zA-Z]+\*?\{', '', text)
    # Remove remaining braces
    text = text.replace('{', '').replace('}', '')
    # Remove leftover \command tokens
    text = re.sub(r'\\[a-zA-Z]+\*?\s*', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _extract_brace_content(text: str, start: int) -> str:
    """Return the content of a brace group where `start` is the index AFTER the opening {."""
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        i += 1
    return text[start:i - 1]


def _extract_bullets(item_list_body: str) -> list[str]:
    """Extract raw bullet strings from \\resumeItem{...} commands (handles nested braces)."""
    bullets = []
    marker = r'\resumeItem{'
    i = 0
    while True:
        idx = item_list_body.find(marker, i)
        if idx == -1:
            break
        start = idx + len(marker)
        depth = 1
        j = start
        while j < len(item_list_body) and depth > 0:
            if item_list_body[j] == '{':
                depth += 1
            elif item_list_body[j] == '}':
                depth -= 1
            j += 1
        bullets.append(item_list_body[start:j - 1].strip())
        i = j
    return bullets


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_latex(latex: str) -> dict:
    """Parse a LaTeX resume into structured plain-text data.

    Returns:
        {
            "experiences": [Experience(...)],
            "projects":    [Project(...)]
        }
    """
    body = extract_latex_body(latex)
    experiences: list[Experience] = []
    projects: list[Project] = []

    # Matches \resumeSubheading with 4 simple (no-nested-brace) args across up to 2 lines
    subheading_re = re.compile(
        r'\\resumeSubheading\s*\{([^}]*)\}\{([^}]*)\}\s*\{([^}]*)\}\{([^}]*)\}',
        re.DOTALL,
    )
    # Match up to and including the opening { of the first arg
    proj_re = re.compile(r'\\resumeProjectHeading\s*\{')
    item_list_re = re.compile(r'\\resumeItemListStart(.*?)\\resumeItemListEnd', re.DOTALL)

    for il in item_list_re.finditer(body):
        before = body[: il.start()]

        last_sh = None
        for m in subheading_re.finditer(before):
            last_sh = m

        last_ph = None
        for m in proj_re.finditer(before):
            last_ph = m

        bullets = [_strip_latex(b) for b in _extract_bullets(il.group(1))]

        sh_pos = last_sh.start() if last_sh else -1
        ph_pos = last_ph.start() if last_ph else -1

        if sh_pos > ph_pos and last_sh:
            experiences.append(Experience(
                role=last_sh.group(1).strip(),
                date=last_sh.group(2).strip(),
                company=last_sh.group(3).strip(),
                location=last_sh.group(4).strip(),
                bullets=bullets,
            ))
        elif last_ph:
            # Extract first arg of \resumeProjectHeading using brace counting
            arg1 = _extract_brace_content(before, last_ph.end())
            parts = arg1.split(' $|$ ', 1)
            title_raw = parts[0]
            tech = _strip_latex(parts[1]) if len(parts) > 1 else ''
            href_match = re.search(r'\\href\{([^{}]*)\}', title_raw)
            link = href_match.group(1) if href_match else ''
            title = _strip_latex(title_raw)
            projects.append(Project(
                title=title,
                tech=tech,
                link=link,
                bullets=bullets,
            ))

    # --- Skills ---
    skills = Skills()
    skills_match = re.search(
        r'\\section\{Technical Skills\}(.*?)(?=\\section\{|\Z)', body, re.DOTALL
    )
    if skills_match:
        skill_items = []
        for m in re.finditer(r'\\textbf\{([^}]+)\}\{:\s*([^}]+)\}', skills_match.group(1)):
            category = _strip_latex(m.group(1))
            values   = _strip_latex(m.group(2))
            skill_items.append(f"{category}: {values}")
        skills = Skills(items=skill_items)

    return {'experiences': experiences, 'projects': projects, 'skills': skills}

if __name__ == "__main__":
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, content FROM docs WHERE id = 4;")
            doc = cur.fetchone()
            print(doc['content'])
            print(parse_latex(doc['content']))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profile WHERE id = 1;")
            profile = cur.fetchone()
            print(profile)
            print(fmt_profile(profile))


    