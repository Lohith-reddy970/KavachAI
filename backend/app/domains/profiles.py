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
        name="General / everyday documents",
        description="A starting point for any document: notes, reports, letters, and personal records.",
        risk_terms=MappingProxyType({
            "high": (
                "critical", "urgent", "severe", "hazard", "unsafe", "breach",
                "violation", "failed", "failure", "exposure", "non-compliant",
                "noncompliant", "crack",
            ),
            "medium": (
                "risk", "issue", "delay", "overdue", "missing", "deviation",
                "anomal", "defect", "damage", "error", "concern", "blocked",
                "discrepancy", "exception", "vibration", "not confirmed", "unresolved",
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
    **{
        profile_id: AnalysisProfile(
            id=profile_id, name=name, description=description,
            risk_terms=MappingProxyType({
                severity: tuple(dict.fromkeys((*base_terms, *extra_terms.get(severity, ()))))
                for severity, base_terms in {
                    "high": ("critical", "urgent", "breach", "violation", "failed", "unsafe"),
                    "medium": ("risk", "delay", "overdue", "missing", "issue", "unresolved", "not confirmed"),
                    "low": ("pending", "follow-up", "recommend", "review required"),
                }.items()
            }),
        )
        for profile_id, name, description, extra_terms in (
            ("business", "Business & projects", "Project updates, meeting notes, suppliers, deadlines, and approvals.", {
                "high": ("blocked", "cancelled"), "medium": ("budget overrun", "not approved", "unassigned", "scope change"),
                "low": ("action item", "sign-off"),
            }),
            ("education", "Education & research", "Assignments, course notes, research reports, and academic administration.", {
                "high": ("plagiarism", "academic misconduct"),
                "medium": ("late submission", "incomplete", "uncited", "withdrawn", "limitation"),
                "low": ("revision", "resubmit"),
            }),
            ("finance", "Finance & procurement", "Invoices, expense records, budgets, payments, and purchase requests.", {
                "high": ("fraud", "unauthorized", "unapproved payment"),
                "medium": ("unpaid", "outstanding", "duplicate", "mismatch", "over budget", "late payment"),
                "low": ("reconcile", "receipt required"),
            }),
            ("legal", "Contracts & policies", "Agreements, obligations, renewals, and policy documents.", {
                "high": ("termination", "liability", "penalty"),
                "medium": ("expired", "unsigned", "dispute", "non-compliance", "renewal", "obligation"),
                "low": ("notice period", "clarification"),
            }),
            ("healthcare", "Healthcare administration", "Administrative records, scheduling, consent forms, and service procedures.", {
                "high": ("privacy incident", "consent withdrawn"),
                "medium": ("unsigned consent", "incomplete record", "missed appointment", "unavailable"),
                "low": ("follow up", "reschedule"),
            }),
            ("hr", "People & HR", "Onboarding, staff policies, training records, and leave administration.", {
                "high": ("harassment", "discrimination", "data exposure"),
                "medium": ("incomplete onboarding", "training gap", "unapproved leave", "grievance"),
                "low": ("probation", "follow up"),
            }),
        )
    },
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
        "description": "Extract dates, amounts, contacts, owners, reference IDs, and measurements with source citations.",
    },
)
ANALYSIS_MODE_IDS = frozenset(mode["id"] for mode in ANALYSIS_MODES)


def get_profile(profile_id: str) -> AnalysisProfile:
    """Return a configured profile or raise ``KeyError`` for an unknown id."""
    return PROFILES[profile_id.strip().lower()]


def list_profiles() -> list[dict[str, str]]:
    return [profile.public_dict() for profile in PROFILES.values()]
