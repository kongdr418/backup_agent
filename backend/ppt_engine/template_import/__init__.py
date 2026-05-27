"""Template import system for PPTX template analysis and SVG extraction.

This package provides the template-import pipeline: PPTX upload -> render ->
classify pages -> extract assets -> templateize SVGs -> install layout pack.

Public surface:
    - Pipeline: runs the import state machine
    - LLMClient: LLM-assisted template analysis
    - merge_llm_plan: merge LLM recommendations into review draft
    - inline_svg_asset_refs: inline image references in SVGs
    - preview_templateized: build preview for review
    - initialize_import: create initial import state
    - run_import: execute full pipeline
    - confirm_import: materialize reviewed draft into layout pack
    - get_review / update_review: review draft CRUD
    - get_status: read import state
    - list_user_templates: enumerate installed templates
    - remove_user_template / rename_user_template: template management
"""

from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

from ppt_engine.config import settings

from . import persistence
from .llm_client import LLMClient, merge_llm_plan
from .pipeline import Pipeline, inline_svg_asset_refs, preview_templateized
from .types import (
    ImportResult,
    ImportTaskState,
    PipelineContext,
    ReviewDraft,
)


# ID + label helpers

def _label_from_name(pptx_name: str) -> str:
    return Path(pptx_name).stem.replace("_", " ").replace("-", " ").title()


def _generate_template_id(pptx_name: str, import_id: str | None = None) -> str:
    stem = Path(pptx_name).stem
    safe = "".join(c if c.isalnum() else "_" for c in stem.lower()).strip("_") or "template"
    digest_seed = f"{stem}:{import_id or ''}"
    short_hash = hashlib.sha1(digest_seed.encode("utf-8")).hexdigest()[:6]
    return f"user_{safe}_{short_hash}"


def _build_context(
    import_id: str,
    pptx_path: Path,
    label: str | None,
    model_config: dict[str, Any] | None,
) -> PipelineContext:
    work_dir = settings.workspaces_dir / "template_imports" / import_id
    work_dir.mkdir(parents=True, exist_ok=True)
    return PipelineContext(
        import_id=import_id,
        work_dir=work_dir,
        pptx_path=pptx_path,
        label=label or _label_from_name(pptx_path.name),
        model_config=dict(model_config or {}),
    )


# Facade

def initialize_import(
    import_id: str,
    pptx_path: Path,
    *,
    label: str | None = None,
) -> str:
    """Create the initial work_dir + state.json. Returns the assigned template_id."""
    template_id = _generate_template_id(pptx_path.name, import_id)
    ctx = _build_context(import_id, pptx_path, label, None)
    state = persistence.read_state(import_id) or {}
    state.setdefault("import_id", import_id)
    state["template_id"] = template_id
    state.setdefault("label", ctx.label)
    state.setdefault("source_file", str(pptx_path))
    state.setdefault("status", "processing")
    state.setdefault("stage", "uploaded")
    state.setdefault("progress", 0.0)
    state.setdefault("review_required", False)
    state.setdefault("steps", [])
    persistence.write_state(import_id, state)
    return template_id


async def run_import(
    import_id: str,
    pptx_path: Path,
    *,
    label: str | None = None,
    model_config: dict[str, Any] | None = None,
) -> ImportResult:
    """Run the full pipeline up to review_required (or error)."""
    ctx = _build_context(import_id, pptx_path, label, model_config)
    pipeline = Pipeline(ctx)
    return await pipeline.run(ctx)


async def retry_import_step(
    import_id: str,
    step_id: str,
    *,
    pptx_path: Path | None = None,
    label: str | None = None,
    model_config: dict[str, Any] | None = None,
) -> ImportResult:
    """Reset step_id (and later steps) to pending, then re-run."""
    state = persistence.read_state(import_id)
    if state is None:
        raise FileNotFoundError(import_id)
    pptx = pptx_path or Path(state.get("source_file") or "")
    ctx = _build_context(import_id, pptx, label or state.get("label"), model_config)
    pipeline = Pipeline(ctx)
    return await pipeline.retry_step(import_id, step_id)


async def confirm_import(import_id: str) -> ImportResult:
    """Materialize the reviewed draft into a layout pack."""
    state = persistence.read_state(import_id)
    if state is None:
        raise FileNotFoundError(import_id)
    pptx = Path(state.get("source_file") or "")
    ctx = _build_context(import_id, pptx, state.get("label"), None)
    pipeline = Pipeline(ctx)
    return await pipeline.confirm(import_id)


def get_review(import_id: str) -> ReviewDraft | None:
    """Read the current review draft, or None if absent."""
    return persistence.read_review(import_id)


def update_review(import_id: str, draft: dict[str, Any]) -> ReviewDraft:
    """Merge user-supplied draft fields into review.json and persist."""
    review = persistence.read_review(import_id)
    if review is None:
        raise FileNotFoundError(import_id)

    if "label" in draft and draft["label"] is not None:
        review["label"] = str(draft["label"]).strip() or review.get("label", "")  # type: ignore[typeddict-item]
    if "page_selections" in draft and isinstance(draft["page_selections"], dict):
        selections = dict(review.get("page_selections") or {})
        for pt in ("cover", "toc", "chapter", "content", "ending"):
            if pt in draft["page_selections"]:
                value = draft["page_selections"][pt]
                selections[pt] = int(value) if value else None
        review["page_selections"] = selections  # type: ignore[typeddict-item]
    if "assets" in draft and isinstance(draft["assets"], dict):
        assets = dict(review.get("assets") or {})
        for asset_id, value in draft["assets"].items():
            if not isinstance(value, dict):
                continue
            entry = dict(assets.get(asset_id) or {})
            entry["asset_id"] = asset_id
            if value.get("role") is not None:
                entry["role"] = str(value["role"])
            if value.get("name") is not None:
                entry["name"] = str(value["name"])
            entry["role_source"] = "user"
            assets[asset_id] = entry  # type: ignore[assignment]
        review["assets"] = assets  # type: ignore[typeddict-item]
    if "preserve_texts" in draft and isinstance(draft["preserve_texts"], list):
        review["preserve_texts"] = [str(item) for item in draft["preserve_texts"] if str(item).strip()]  # type: ignore[typeddict-item]
    if "placeholder_hints" in draft and isinstance(draft["placeholder_hints"], dict):
        hints: dict[str, dict[str, str]] = {}
        for page_type, values in draft["placeholder_hints"].items():
            if not isinstance(values, dict):
                continue
            hints[str(page_type)] = {str(name): str(original) for name, original in values.items() if str(name).strip()}
        review["placeholder_hints"] = hints  # type: ignore[typeddict-item]
    if "element_actions" in draft and isinstance(draft["element_actions"], list):
        review["element_actions"] = [dict(item) for item in draft["element_actions"] if isinstance(item, dict)]  # type: ignore[typeddict-item]
    if "design_spec" in draft and draft["design_spec"] is not None:
        review["design_spec_md"] = str(draft["design_spec"])  # type: ignore[typeddict-item]

    persistence.write_review(import_id, review)
    return review


def get_status(import_id: str) -> dict[str, Any] | None:
    """Read the persisted state.json for an import task."""
    return persistence.read_state(import_id)


def rename_user_template(template_id: str, label: str) -> bool:
    return persistence.rename_user_template(template_id, label)


def remove_user_template(template_id: str) -> bool:
    return persistence.remove_user_template(template_id)


def list_user_templates() -> list[dict[str, Any]]:
    """Read the user_templates.json index as a flat list of rows."""
    index_path = persistence._layouts_root() / "user_templates.json"
    raw = persistence._read_json_or_none(index_path)
    if not isinstance(raw, dict):
        return []
    templates = raw.get("templates")
    if not isinstance(templates, dict):
        return []
    out: list[dict[str, Any]] = []
    for tid, row in templates.items():
        if not isinstance(row, dict):
            continue
        out.append({
            "template_id": tid,
            "label": row.get("label", tid),
            "summary": row.get("summary", ""),
            "slide_count": row.get("slide_count", row.get("slideCount", 0)),
        })
    out.sort(key=lambda r: r["template_id"])
    return out


__all__ = [
    "Pipeline", "PipelineContext", "LLMClient", "merge_llm_plan",
    "inline_svg_asset_refs", "initialize_import", "run_import",
    "retry_import_step", "confirm_import", "get_review", "get_status",
    "update_review", "rename_user_template", "remove_user_template",
    "list_user_templates", "preview_templateized",
]
