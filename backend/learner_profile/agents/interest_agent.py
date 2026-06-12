from __future__ import annotations

from typing import Any


class InterestAgent:
    """Extract interests only from explicit student or high-confidence signals."""

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
            signal = payload.get("interest_direction") if isinstance(payload, dict) else None
            if not isinstance(signal, dict):
                continue
            label = str(signal.get("label") or "").strip()
            confidence = float(signal.get("confidence", 0) or 0)
            if not label or confidence < 0.75:
                continue
            proposals.append(
                {
                    "type": "interest_direction_update",
                    "scope": "global",
                    "trait_key": label,
                    "before": None,
                    "after": {
                        "label": label,
                        "weight": max(0.0, min(1.0, float(signal.get("weight", 0.5)))),
                        "confidence": confidence,
                        "source": str(signal.get("source") or "inferred"),
                        "evidence_ids": [event.get("id", "")],
                    },
                    "confidence": confidence,
                    "reason": str(signal.get("reason") or "根据学生主动表达归纳兴趣方向。"),
                    "evidence_ids": [event.get("id", "")],
                }
            )
        return proposals
