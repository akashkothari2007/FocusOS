"""Prompt templates for AI calls."""

import re


def extract_latex_body(latex: str) -> str:
    """Strip preamble — only send content between begin/end document to save tokens."""
    match = re.search(r'\\begin\{document\}(.*?)\\end\{document\}', latex, re.DOTALL)
    return match.group(1).strip() if match else latex


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


def step1_messages(job_description: str, resume: str, profile_ctx: str) -> list[dict]:
    """Match score + ATS keywords. Sends body-only resume to save tokens."""
    resume_body = extract_latex_body(resume)
    profile_block = (
        f"Additional candidate context (not yet on resume):\n{profile_ctx}\n\n"
        if profile_ctx else ""
    )
    return [
        {
            "role": "system",
            "content": (
                "You are a strict ATS system and resume screener. "
                "Score calibration: 0-30 = weak, 31-55 = partial, 56-75 = decent, "
                "76-90 = strong, 91-100 = near-perfect. "
                "Most candidates score 35-65. Do not inflate. "
                "Penalise clearly missing hard requirements (e.g. required languages, frameworks, domain experience). "
                "Always respond with valid JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Job Description:\n{job_description}\n\n"
                f"Resume:\n{resume_body}\n\n"
                + profile_block
                + "1. Score how well this candidate matches the job RIGHT NOW based on what is demonstrated. "
                "2. Extract the top 12-15 ATS keywords from the job description — these are the exact terms "
                "an ATS would scan for (technologies, methodologies, domain terms).\n"
                'Return JSON: {"match_score": <integer 0-100>, "keywords": [<string>, ...]}'
            ),
        },
    ]


def step2_messages(
    keywords: list[str], job_description: str, resume: str, profile_ctx: str
) -> list[dict]:
    """Actionable suggestions. Tells AI exactly what format suggestions should take."""
    resume_body = extract_latex_body(resume)
    profile_block = (
        f"Additional candidate context (not yet on resume):\n{profile_ctx}\n\n"
        if profile_ctx else ""
    )
    return [
        {
            "role": "system",
            "content": (
                "You are a direct, honest resume coach helping a candidate tailor their resume. "
                "You only work with what the candidate has actually done — never invent experience. "
                "If a requirement is genuinely missing, say so clearly instead of suggesting they fake it. "
                "Always respond with valid JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Target ATS Keywords: {', '.join(keywords)}\n\n"
                f"Job Description:\n{job_description}\n\n"
                f"Current Resume:\n{resume_body}\n\n"
                + profile_block
                + "Give 6-10 specific, actionable suggestions to better tailor this resume. "
                "Each suggestion must:\n"
                "- Reference a specific bullet, section, or project by name\n"
                "- Say exactly what to change or add (e.g. 'In the RamSoft bullet about MedASR, add that this involved real-time data pipeline design')\n"
                "- Explain which keyword or requirement it targets\n"
                "- If a project from the additional context should be added to the resume, say which one and why\n"
                "- If a hard requirement is simply missing from the candidate's background, state it plainly: 'Candidate has no demonstrated experience with X — do not fabricate'\n"
                'Return JSON: {"suggestions": [<string>, ...]}'
            ),
        },
    ]


def resume_messages(
    base_resume: str,
    keywords: list[str],
    suggestions: list[str],
    profile_ctx: str,
    job_description: str,
) -> list[dict]:
    """Generate tailored LaTeX resume. Sends full LaTeX since we need to rewrite it."""
    profile_block = (
        f"Additional candidate context:\n{profile_ctx}\n\n"
        if profile_ctx else ""
    )
    keywords_str = ", ".join(keywords) if keywords else "none"
    suggestions_block = "\n".join(f"- {s}" for s in suggestions) if suggestions else "none"

    return [
        {
            "role": "system",
            "content": (
                "You are an expert LaTeX resume writer. "
                "You tailor resumes by reframing and expanding on real experience — never by fabricating it. "
                "You preserve LaTeX structure exactly. You never add extra packages or commands. "
                "Always respond with valid JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Base Resume (LaTeX):\n{base_resume}\n\n"
                f"Job Description:\n{job_description}\n\n"
                + profile_block
                + f"ATS Keywords to incorporate: {keywords_str}\n\n"
                f"Suggestions to apply:\n{suggestions_block}\n\n"
                "Rewrite the resume in LaTeX following these rules STRICTLY:\n"
                "1. Keep the ENTIRE preamble (\\documentclass through all \\newcommand definitions) IDENTICAL — do not change a single character\n"
                "2. Only modify text inside \\resumeItem{{}}, \\resumeSubheading{{}}, and \\resumeProjectHeading{{}} commands\n"
                "3. Incorporate keywords naturally where the candidate's background genuinely supports it\n"
                "4. Apply the suggestions where applicable\n"
                "5. STRICT ONE PAGE: keep the same number of bullet points as the base resume — do not add bullets, only reword existing ones\n"
                "6. End with \\end{{document}} and absolutely nothing after it\n"
                "7. Do not add any text, comments, or notes outside of LaTeX commands\n"
                "8. NEVER use \\\\ inside any argument to \\resumeProjectHeading, \\resumeSubheading, \\textbf, \\href, or \\emph. If a title is too long, shorten it instead.\n"
                'Return JSON: {"resume": "<complete LaTeX source>"}'
            ),
        },
    ]