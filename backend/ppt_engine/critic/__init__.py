"""SVG critic modules."""

from .static_critic import check_svg, CriticConfig, CriticReport, Violation
from .visual_critic import VisualCheckOutcome, VisualCriticConfig, visual_check

__all__ = [
    "check_svg",
    "CriticConfig",
    "CriticReport",
    "Violation",
    "visual_check",
    "VisualCriticConfig",
    "VisualCheckOutcome",
]
