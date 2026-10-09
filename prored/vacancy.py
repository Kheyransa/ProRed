"""Editable demo vacancy data; independent of AI mode and providers."""
from prored.intake import normalize_skills

DEMO_TITLE = "Junior Python / FastAPI Developer"
DEMO_DESCRIPTION = (
    "We are looking for a junior developer to build and maintain Python APIs using FastAPI. "
    "Responsibilities include creating endpoints, validating input, working with SQL databases, "
    "handling errors, and writing unit tests. Candidates should be able to explain their technical "
    "decisions and handle common edge cases."
)
DEMO_SKILLS = ["Python", "FastAPI", "SQL", "Input validation", "Error handling", "Unit testing"]
SKILL_OPTIONS = ["Python", "FastAPI", "SQL", "Input validation", "Error handling", "Unit testing", "Testing", "Git", "Django", "Flask", "Data analysis"]


def vacancy_data(title, description, selected, manual):
    return {"title": title.strip(), "description": description.strip(), "skills": normalize_skills(selected + manual.splitlines())}
