"""Validated model contracts, kept separate from the candidate UI."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SkillSuggestions(Contract):
    skills: list[str] = Field(max_length=40)


class ProjectClaim(Contract):
    name: str
    description: str


class CVClaims(Contract):
    skills: list[str] = Field(max_length=60)
    projects: list[ProjectClaim] = Field(max_length=20)


class Evidence(Contract):
    skill: str
    claim: str
    status: Literal["Supported", "Partially supported", "Not found in inspected files", "Cannot assess"]
    source_ids: list[str] = Field(max_length=8)
    explanation: str
    uncertainty: str


class Comparison(Contract):
    evidence: list[Evidence]
    uncertainties: list[str]


class RubricCriterion(Contract):
    criterion: str
    expected: str


class InterviewItem(Contract):
    kind: Literal["question", "coding"]
    skill: str
    difficulty: Literal["easy", "medium", "hard"]
    prompt: str
    source_id: str | None
    general: bool
    starter_code: str
    expected_answer: str
    rubric: list[RubricCriterion] = Field(min_length=1, max_length=6)


class InterviewPlan(Contract):
    items: list[InterviewItem] = Field(min_length=3, max_length=3)


class CriterionObservation(Contract):
    criterion: str
    finding: str
    result: Literal["met", "partly met", "not met", "cannot assess"]


class Review(Contract):
    level: Literal["weak", "partial", "strong"]
    observations: list[CriterionObservation]
    summary: str
    uncertainty: str
