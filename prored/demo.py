"""Explicit illustrative fixtures; never silently used for live failures."""
from prored.github import ProfileScan, RepositoryOption
from prored.schemas import CVClaims, Comparison, CriterionObservation, Evidence, InterviewItem, InterviewPlan, ProjectClaim, Review, RubricCriterion, SkillSuggestions
from prored.sources import Snapshot, build_sources

DEMO_REPOSITORY = "https://github.com/prored-demo/python-inventory"
DEMO_FILES = {
    "README.md": "# Python inventory\nA small demo for Python validation and testing.\nSQL storage is planned, not implemented.\n",
    "requirements.txt": "pytest>=8\n",
    "inventory.py": '''def total_price(items):
    """Sum non-negative prices; reject negative prices."""
    total = 0
    for price in items:
        if price < 0:
            raise ValueError("negative price")
        total += price
    return total
''',
    "tests/test_inventory.py": '''import pytest
from inventory import total_price

def test_total():
    assert total_price([2, 3]) == 5

def test_negative():
    with pytest.raises(ValueError):
        total_price([-1])
''',
}


def demo_snapshot(url=None):
    docs = url == "https://github.com/prored-demo/docs"
    files = {"README.md": "# Documentation-only mock fixture\nNo Python implementation is available.\n"} if docs else dict(DEMO_FILES)
    snapshot = Snapshot(url if docs else DEMO_REPOSITORY, "a" * 40, files, ["Mock fixture: no real GitHub fetch occurred."], False, len(files), True)
    build_sources(snapshot)
    return snapshot


def demo_profile():
    options = [RepositoryOption(DEMO_REPOSITORY, "Illustrative inventory and tests", "Python", ["testing"], False, 4, "Mock suggestion: Python implementation and pytest declarations; not evidence of authorship."), RepositoryOption("https://github.com/prored-demo/docs", "Illustrative documentation", "Unknown", [], False, 0, "Mock alternative; less relevant to Python.")]
    return ProfileScan(options, DEMO_REPOSITORY, ["Mock profile list, not fetched from the entered GitHub profile."])


class MockProvider:
    mode = "mock"

    def generate(self, task, payload, schema):
        if schema is SkillSuggestions:
            jd = payload.get("job_description", "").lower()
            return SkillSuggestions(skills=[s for s in ["Python", "SQL", "Testing", "Django", "FastAPI", "Git"] if s.lower() in jd])
        if schema is CVClaims:
            text = payload["text"].lower()
            skills = [s for s in ["Python", "SQL", "Testing", "Git", "Django", "FastAPI"] if s.lower() in text]
            projects = [ProjectClaim(name="Inventory", description="Candidate mentions an inventory project.")] if "inventory" in text else []
            return CVClaims(skills=skills, projects=projects)
        if schema is Comparison:
            evidence = []
            for skill in payload["skills"]:
                sources = [s for s in payload["sources"] if (skill.lower() == "python" and s["kind"] == "Source implementation") or (skill.lower() == "testing" and s["kind"] == "Test implementation")]
                claim = next((c for c in payload["claims"] if skill.lower() in c.lower()), "")
                evidence.append(Evidence(skill=skill, claim=claim, status="Supported" if sources else "Not found in inspected files", source_ids=[s["source_id"] for s in sources[:2]], explanation="Illustrative mock keyword/fixture observation; not a real AI assessment.", uncertainty="Only inspected snippets; authorship and wider proficiency are unknown."))
            return Comparison(evidence=evidence, uncertainties=["Mock mode: findings are deterministic illustrations, not candidate evaluation."])
        if schema is InterviewPlan:
            skills = payload["skills"]
            return InterviewPlan(items=[self._item("question", skills[0], "medium", payload), self._item("question", skills[1 % len(skills)], "medium", payload), self._item("coding", skills[0], "medium", payload)])
        if schema is InterviewItem:
            return self._item(payload["kind"], payload["skill"], payload["difficulty"], payload)
        if schema is Review:
            answer = payload["answer"].lower()
            # Explicit mock heuristic solely for demonstrating adaptive paths.
            level = "weak" if len(answer.strip()) < 20 else "strong" if ("raise" in answer and "empty" in answer) or ("edge" in answer and "validation" in answer) else "partial"
            result = {"weak": "not met", "partial": "partly met", "strong": "met"}[level]
            return Review(level=level, observations=[CriterionObservation(criterion=r["criterion"], finding="Mock length/keyword heuristic; not a technical correctness finding.", result=result) for r in payload["rubric"]], summary="Illustrative mock review only.", uncertainty="Code was not executed; mock review cannot establish understanding or correctness.")
        raise ValueError("Unsupported mock contract")

    def _item(self, kind, skill, difficulty, payload):
        sources = payload.get("sources", [])
        preferred = "Test implementation" if skill.lower() == "testing" else "Source implementation"
        source = next((s for s in sources if s["kind"] == preferred), None) if skill.lower() in {"python", "testing"} else None
        if kind == "coding":
            prompt = "Implement safe_total(items): sum non-negative numeric prices, reject negative values, and return 0 for empty input. Explain edge cases in comments."
            starter = "def safe_total(items):\n    # Write your implementation and edge-case notes here.\n    pass\n"
            expected = "Loop over prices, reject negatives with ValueError, accumulate and return total; empty input returns zero. Discuss input types."
        else:
            prompt = "Explain the referenced function/test, its validation behavior and edge cases. What does this snippet leave unverified?" if source else f"General skill question: explain a concrete use of {skill}, its constraints, and how you would validate it."
            starter = ""
            expected = "Explain behavior and validation, identify empty/invalid input or failure scenarios, and propose meaningful checks without claiming tests ran."
        if payload.get("followup"):
            prompt = {"easy": "Break the problem down: " , "medium": "Clarify your reasoning: ", "hard": "Extend the reasoning to invalid types and larger inputs: "}[difficulty] + prompt
        return InterviewItem(kind=kind, skill=skill, difficulty=difficulty, prompt=prompt, source_id=source["source_id"] if source else None, general=source is None, starter_code=starter, expected_answer=expected, rubric=[RubricCriterion(criterion="Behavior and logic", expected=expected), RubricCriterion(criterion="Edge cases and clarity", expected="Discuss empty input, invalid values, limitations and readable reasoning.")])
