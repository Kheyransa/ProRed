"""Atomic assessment transitions independent of Streamlit reruns."""
from copy import deepcopy
from dataclasses import dataclass, field

from prored.schemas import InterviewItem, InterviewPlan, Review

MAX_FOLLOWUPS = 1


@dataclass
class Attempt:
    item_id: str
    item: InterviewItem
    parent_id: str | None = None
    answer: str | None = None
    review: Review | None = None


@dataclass
class Assessment:
    attempts: list[Attempt]
    max_followups: int = MAX_FOLLOWUPS
    mode: str = "mock"

    @classmethod
    def from_plan(cls, plan: InterviewPlan, mode: str, max_followups: int = MAX_FOLLOWUPS):
        if max_followups not in {0, 1}:
            raise ValueError("MVP permits zero or one follow-up per initial item.")
        if [i.kind for i in plan.items].count("question") != 2 or [i.kind for i in plan.items].count("coding") != 1:
            raise ValueError("Plan must contain two questions and one coding task.")
        return cls([Attempt(f"initial-{index + 1}", item) for index, item in enumerate(plan.items)], max_followups, mode)

    @property
    def current(self) -> Attempt | None:
        return next((a for a in self.attempts if a.review is None), None)

    @property
    def complete(self) -> bool:
        return self.current is None

    def record(self, item_id: str, answer: str, review: Review, followup: InterviewItem | None):
        current = self.current
        if not current or current.item_id != item_id or not answer.strip():
            raise ValueError("Submission is empty, stale, or already reviewed.")
        need_followup = current.parent_id is None and self.max_followups == 1
        if need_followup != (followup is not None):
            raise ValueError("Follow-up must be prepared before committing this submission.")
        if followup and (followup.skill != current.item.skill or followup.kind != current.item.kind or followup.difficulty != next_difficulty(current.item.difficulty, review.level)):
            raise ValueError("Follow-up does not match the adaptive path.")
        current.answer, current.review = answer, review
        if followup:
            index = self.attempts.index(current) + 1
            self.attempts.insert(index, Attempt(current.item_id + "-followup", followup, current.item_id))


def next_difficulty(difficulty: str, level: str) -> str:
    levels = ["easy", "medium", "hard"]
    shift = {"weak": -1, "partial": 0, "strong": 1}[level]
    return levels[max(0, min(2, levels.index(difficulty) + shift))]
