"""Unified logging for ppt_engine.

Provides a logger with consistent formatting and helpers for logging
AI-generated content at appropriate verbosity levels.
"""

from __future__ import annotations

import logging
import textwrap


# Shared logger instance for the entire ppt_engine package
_logger: logging.Logger | None = None


def get_logger(name: str = "ppt_engine") -> logging.Logger:
    """Return the ppt_engine logger.

    Relies on the root logger handler configured by Flask (app.py).
    Does NOT add its own handler to avoid duplicate output.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    return logger


def _truncate(text: str, max_len: int = 800) -> str:
    """Truncate text with ellipsis if it exceeds max_len."""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n... ({len(text) - max_len} chars truncated)"


def log_llm_request(
    logger: logging.Logger,
    model: str,
    messages: list,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> None:
    """Log an outgoing LLM request with message summary."""
    # Build a compact message summary
    summary_parts: list[str] = []
    for i, msg in enumerate(messages):
        role = getattr(msg, "role", "unknown")
        content = getattr(msg, "content", "")
        if isinstance(content, list):
            content = " ".join(
                getattr(block, "text", str(block)) for block in content
            )
        content_str = str(content) if content else ""
        summary_parts.append(f"  [{i}] {role}: {_truncate(content_str, 400)}")

    msg_summary = "\n".join(summary_parts)
    params = f"model={model}"
    if temperature is not None:
        params += f" temp={temperature}"
    if max_tokens is not None:
        params += f" max_tokens={max_tokens}"

    logger.info("LLM REQUEST | %s\nMessages:\n%s", params, msg_summary)


def log_llm_response(
    logger: logging.Logger,
    model: str,
    content: str,
    duration_ms: int,
    usage: object | None,
) -> None:
    """Log an LLM response with content summary and metrics."""
    usage_str = ""
    if usage is not None:
        prompt = getattr(usage, "prompt_tokens", "?")
        completion = getattr(usage, "completion_tokens", "?")
        usage_str = f" | tokens={prompt}+{completion}"

    truncated = _truncate(content, 1000)
    logger.info(
        "LLM RESPONSE | model=%s | time=%dms%s\nContent:\n%s",
        model, duration_ms, usage_str, truncated,
    )


def log_agent_stage(
    logger: logging.Logger,
    agent_name: str,
    action: str,
    detail: str = "",
) -> None:
    """Log an agent stage transition."""
    if detail:
        logger.info("[%s] %s | %s", agent_name, action, detail)
    else:
        logger.info("[%s] %s", agent_name, action)


def log_agent_output(
    logger: logging.Logger,
    agent_name: str,
    output_name: str,
    content: str,
) -> None:
    """Log the full (truncated) output of an agent."""
    truncated = _truncate(content, 1200)
    logger.info(
        "[%s] OUTPUT | %s (%d chars)\n%s",
        agent_name, output_name, len(content), truncated,
    )


def log_validation_result(
    logger: logging.Logger,
    agent_name: str,
    passed: bool,
    error: str | None = None,
    attempt: int | None = None,
) -> None:
    """Log a validation result (pass / fail with details)."""
    status = "PASS" if passed else "FAIL"
    attempt_str = f" (attempt {attempt})" if attempt else ""
    if error and not passed:
        logger.info("[%s] VALIDATION %s%s | %s", agent_name, status, attempt_str, error)
    else:
        logger.info("[%s] VALIDATION %s%s", agent_name, status, attempt_str)


def log_critic_result(
    logger: logging.Logger,
    page_num: int,
    passed: bool,
    violations: list | None = None,
    attempt: int = 0,
) -> None:
    """Log a critic check result for a single SVG page."""
    status = "PASS" if passed else "FAIL"
    vlist = violations or []
    if vlist:
        vdetails = "\n".join(f"  - {v}" for v in vlist[:5])
        if len(vlist) > 5:
            vdetails += f"\n  ... ({len(vlist) - 5} more)"
        logger.info(
            "[Critic] Page %d | %s (attempt %d) | %d violations:\n%s",
            page_num, status, attempt, len(vlist), vdetails,
        )
    else:
        logger.info(
            "[Critic] Page %d | %s (attempt %d)",
            page_num, status, attempt,
        )
