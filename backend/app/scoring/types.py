"""Shapes shared by the matchers, the score formula and the stored report."""

from dataclasses import asdict, dataclass, field
from typing import Literal

Status = Literal["met", "partial", "missing"]
Importance = Literal["must", "nice"]
Category = Literal["skill", "experience", "education", "other"]


@dataclass
class Line:
    id: str  # "L1"
    text: str


@dataclass
class Requirement:
    id: str  # "R1"
    text: str
    jd_line: str | None
    importance: Importance
    category: Category
    status: Status = "missing"
    evidence: list[str] = field(default_factory=list)  # resume line ids
    note: str = ""

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class MatchResult:
    requirements: list[Requirement]
    engine: str  # "built-in" or "groq:<model>" / "gemini:<model>"
    summary: str | None = None  # an LLM may write one; otherwise the engine writes it
    warnings: list[str] = field(default_factory=list)
