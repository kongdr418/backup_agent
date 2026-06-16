from __future__ import annotations

import hashlib
from typing import Any

from .agents import (
    CognitivePreferenceAgent,
    ErrorDiagnosisAgent,
    InterestAgent,
    TransferAssessmentAgent,
)


class ProfileOrchestrator:
    def __init__(self, llm_call: Any | None = None) -> None:
        self.agents = [
            CognitivePreferenceAgent(),
            InterestAgent(),
            ErrorDiagnosisAgent(),
            TransferAssessmentAgent(),
        ]

    def analyze(
        self,
        *,
        profile: dict[str, Any],
        classroom: dict[str, Any],
        report: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: dict[tuple[str, str, str], dict[str, Any]] = {}
        for agent in self.agents:
            for proposal in agent.analyze(
                profile=profile,
                classroom=classroom,
                report=report,
                events=events,
            ):
                key = (
                    str(proposal.get("type") or ""),
                    str(proposal.get("course_id") or ""),
                    str(proposal.get("trait_key") or ""),
                )
                existing = merged.get(key)
                if existing is None or float(proposal.get("confidence", 0)) > float(
                    existing.get("confidence", 0)
                ):
                    if not proposal.get("id"):
                        raw = "|".join([*key, *proposal.get("evidence_ids", [])])
                        proposal["id"] = (
                            "update_"
                            + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
                        )
                    proposal.setdefault("status", "pending")
                    merged[key] = proposal
        return list(merged.values())
