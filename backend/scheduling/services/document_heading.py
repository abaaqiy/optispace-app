"""Conservative suggestions from the image title, confirmed once in review."""
import re


def parse_heading(text):
    text = str(text or "")[:4000]
    result = {"department": "", "faculty": "", "academic_session": "",
              "semester": "", "source_version": "", "heading_text": text}
    department = re.search(
        r"\bDEPARTMENT\s+OF\s+(.+?)(?=\s*[,;]|\s+FACULTY\b|\n|$)", text, re.I,
    )
    faculty = re.search(r"\b[FКK]ACULTY\s+OF\s+([^\n,;]+)", text, re.I)
    if department:
        result["department"] = department[1].strip().title()[:150]
    if faculty:
        result["faculty"] = "Faculty of " + faculty[1].strip().title()[:135]
    sessions = set(re.findall(r"\b(20\d{2})\s*[/–-]\s*(20\d{2})\b", text))
    if len(sessions) == 1:
        first, last = next(iter(sessions))
        if int(last) == int(first) + 1:
            result["academic_session"] = f"{first}/{last}"
    semesters = set(word.title() for word in re.findall(r"\b(Rain|Harmattan)\b", text, re.I))
    if len(semesters) == 1:
        result["semester"] = semesters.pop()
    version = re.search(r"\b((?:FIRST|SECOND|THIRD|FINAL)\s+DRAFT|REVISED|FINAL)\b", text, re.I)
    if version:
        result["source_version"] = version[1].title()
    return result
