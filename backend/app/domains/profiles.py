"""Configurable domain profiles used by document analysis."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class AnalysisProfile:
    id: str
    name: str
    description: str
    risk_terms: Mapping[str, tuple[str, ...]]

    def public_dict(self) -> dict[str, str]:
        return {"id": self.id, "name": self.name, "description": self.description}


PROFILES: Mapping[str, AnalysisProfile] = MappingProxyType({
    "general": AnalysisProfile(
        id="general",
        name="General documents",
        description="Broad review terms for reports, policies, correspondence, and records.",
        risk_terms=MappingProxyType({
            "high": (
                "critical", "urgent", "severe", "hazard", "unsafe", "breach",
                "violation", "failed", "failure", "exposure", "non-compliant",
                "noncompliant", "crack",
            ),
            "medium": (
                "risk", "issue", "delay", "overdue", "missing", "deviation",
                "anomal", "defect", "damage", "error", "concern", "blocked",
                "discrepancy", "exception", "vibration",
            ),
            "low": (
                "recommend", "monitor", "follow-up", "follow up", "pending",
                "investigat", "review required",
            ),
        }),
    ),
    "industrial": AnalysisProfile(
        id="industrial",
        name="Industrial engineering",
        description="Equipment integrity, maintenance, and process-safety terminology.",
        risk_terms=MappingProxyType({
            "high": (
                "leak", "crack", "ruptur", "fail", "fire", "explosi", "unsafe",
                "hazard", "critical", "breach", "violat", "non-complian",
                "noncomplian", "vulnerab", "below minimum", "exceeds", "exceeded",
                "shutdown",
            ),
            "medium": (
                "corro", "erosion", "wear", "worn", "degrad", "sluggish", "overdue",
                "deviat", "anomal", "defect", "fouling", "vibrat", "damage",
                "warning", "replace", "repair", "overheat",
            ),
            "low": (
                "recommend", "monitor", "follow-up", "follow up", "trend",
                "re-inspect", "reinspect", "investigat",
            ),
        }),
    ),
})


ANALYSIS_MODES = (
    {
        "id": "risk_review",
        "name": "Risk review",
        "description": "Find risk-related statements, quote the source, and verify each excerpt.",
    },
    {
        "id": "summary",
        "name": "Summary",
        "description": "Summarize extracted text or describe a supplied image; output is advisory.",
    },
    {
        "id": "extract_fields",
        "name": "Extract fields",
        "description": "Extract dates, equipment identifiers, and measurements directly from text.",
    },
)
ANALYSIS_MODE_IDS = frozenset(mode["id"] for mode in ANALYSIS_MODES)


def get_profile(profile_id: str) -> AnalysisProfile:
    """Return a configured profile or raise ``KeyError`` for an unknown id."""
    return PROFILES[profile_id.strip().lower()]


def list_profiles() -> list[dict[str, str]]:
    return [profile.public_dict() for profile in PROFILES.values()]
