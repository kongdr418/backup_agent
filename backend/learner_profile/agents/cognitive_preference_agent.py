from __future__ import annotations

from typing import Any


class CognitivePreferenceAgent:
    """Extract conservative cognitive-preference proposals from explicit signals."""

    def analyze(
        self,
        *,
        profile: dict[str, Any],
        classroom: dict[str, Any],
        report: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        for event in events:
            payload = event.get("payload") if isinstance(event, dict) else {}
            signal = payload.get("cognitive_preference") if isinstance(payload, dict) else None
            if not isinstance(signal, dict):
                continue
            key = str(signal.get("key") or "").strip()
            confidence = float(signal.get("confidence", 0) or 0)
            if not key or confidence < 0.7:
                continue
            proposals.append(
                {
                    "type": "cognitive_preference_update",
                    "scope": "global",
                    "trait_key": key,
                    "before": None,
                    "after": {
                        "weight": max(0.0, min(1.0, float(signal.get("weight", 0.5)))),
                        "confidence": confidence,
                        "source": "inferred",
                        "evidence_ids": [event.get("id", "")],
                    },
                    "confidence": confidence,
                    "reason": str(signal.get("reason") or "根据近期学习行为归纳认知偏好。"),
                    "evidence_ids": [event.get("id", "")],
                }
            )
        return proposals
