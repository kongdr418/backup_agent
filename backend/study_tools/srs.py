from __future__ import annotations

from datetime import date, timedelta
from typing import Any


INITIAL_SM2: dict[str, Any] = {
    "repetitions": 0,
    "ease_factor": 2.5,
    "interval_days": 0,
    "due_date": "",
    "last_grade": None,
}


def compute_next_review(
    sm2: dict[str, Any],
    grade: int,
    today: date | None = None,
) -> dict[str, Any]:
    grade = max(0, min(5, int(grade)))
    today = today or date.today()

    ef_prev = float(sm2.get("ease_factor") or 2.5)
    ef = ef_prev + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    ef = max(1.3, round(ef, 4))

    if grade < 3:
        reps = 0
        interval = 1
    else:
        reps = int(sm2.get("repetitions") or 0) + 1
        prev_interval = int(sm2.get("interval_days") or 0)
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = max(1, int(round(prev_interval * ef)))

    due = (today + timedelta(days=interval)).isoformat()
    return {
        "repetitions": reps,
        "ease_factor": ef,
        "interval_days": interval,
        "due_date": due,
        "last_grade": grade,
    }
