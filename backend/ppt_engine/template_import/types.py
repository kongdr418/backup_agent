"""Shared dataclasses, TypedDicts, Pydantic models, and exceptions.

This module is the *single source of truth* for the data shapes used by
every leaf module in :mod:`ppt_engine.template_import` and by
the orchestrating :class:`pipeline.Pipeline`. It contains **no logic**;
only type / data declarations.

Conventions:

* ``@dataclass(frozen=True)`` -- immutable value types passed across module
  boundaries (``PipelineContext``, ``BoundingBox``, ``RenderResult``,
  ``SlideMetrics``, ``PlaceholderInstance``).
* ``@dataclass`` -- mutable aggregates filled in by leaf modules
  (``AssetCandidate``, ``AssetOccurrence``, ``ChromeTextItem``,
  ``ElementAction``, ``PageClassification``, ``TemplateizeOutput``,
  ``ImportResult``, ``InstallResult``, ``LayoutPack``).
* ``TypedDict`` (``total=False``) -- JSON-shaped objects persisted to
  disk. They round-trip through ``json.dumps``/``json.loads`` and are
  expected to preserve unknown forward-compatible fields untouched.
* ``BaseModel`` -- Pydantic v2 models for the LLM-validated structures
  (``LLMTemplateImportPlan`` and its sub-models), which require strict
  schema enforcement and structured retry on parse failure.

All timestamps are Unix seconds (``float``); paths are :class:`pathlib.Path`;
coordinates default to viewBox pixels unless otherwise noted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


# Literal aliases
PageType = Literal["cover", "toc", "chapter", "content", "ending"]
AssetRole = Literal["logo", "background", "decoration", "content_image", "ignore"]
AssetLayer = Literal["master", "layout", "slide"]
ElementActionLabel = Literal["keep", "remove", "replace_with_placeholder"]
RoleSource = Literal["rule", "llm", "user"]
ExportMode = Literal["powerpoint-com", "libreoffice"]
StepStatus = Literal["pending", "active", "complete", "error", "skipped"]
TaskStatus = Literal["processing", "review_required", "complete", "error"]
ErrorKind = Literal["render", "extraction", "llm", "persistence", "unknown"]
PlaceholderName = Literal[
    "TITLE", "PAGE_TITLE", "SUBTITLE", "AUTHOR", "DATE",
    "CHAPTER_NUM", "CHAPTER_NUMBER", "CHAPTER_TITLE",
    "TOC_LIST", "TOC_ITEM_1", "TOC_ITEM_2", "TOC_ITEM_3",
    "TOC_ITEM_4", "TOC_ITEM_5", "CONTENT_AREA",
    "ENDING_TITLE", "ENDING_MESSAGE", "LOGO_HEADER", "LOGO_FOOTER",
]
ChatRole = Literal["user", "assistant", "system"]
ManifestWarningCode = Literal[
    "asset-too-large", "asset-decode-failed",
    "templateize.geometry_violation", "renderer.fallback",
    "llm.placeholder_rejected", "render.empty_slide",
]


# Exceptions

class TemplateImportError(Exception):
    error_kind: ErrorKind = "unknown"

    def __init__(
        self,
        reason: str,
        *,
        step_id: str | None = None,
        error_kind: ErrorKind | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.step_id = step_id
        if error_kind is not None:
            self.error_kind = error_kind
        self.context: dict[str, Any] = dict(context) if context else {}


class RenderError(TemplateImportError):
    error_kind: ErrorKind = "render"


class ExtractionError(TemplateImportError):
    error_kind: ErrorKind = "extraction"


class LLMPlanError(TemplateImportError):
    error_kind: ErrorKind = "llm"


class PersistenceError(TemplateImportError):
    error_kind: ErrorKind = "persistence"


# Geometry & rendering value types

@dataclass(frozen=True)
class BoundingBox:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class SlideMetrics:
    slide_index: int
    canvas_width: int
    canvas_height: int
    font_substitutions: dict[str, str]
    rendered_at: float


@dataclass(frozen=True)
class RenderResult:
    svg_files: list[Path]
    slide_metrics: list[SlideMetrics]
    export_mode: ExportMode
    canvas: tuple[int, int]


# Pipeline context

@dataclass(frozen=True)
class PipelineContext:
    import_id: str
    work_dir: Path
    pptx_path: Path
    label: str
    model_config: dict[str, Any]


# Asset extraction

@dataclass
class AssetOccurrence:
    slide_index: int
    x: float
    y: float
    width: float
    height: float
    layer: AssetLayer


@dataclass
class AssetCandidate:
    asset_id: str
    file_name: str
    pages: list[int]
    occurrences: list[AssetOccurrence]
    sha1: str
    phash: str | None = None
    bytes: int = 0
    mime: str = "application/octet-stream"
    width_px: int | None = None
    height_px: int | None = None
    position_stable: bool = False
    recommended_role: AssetRole = "decoration"
    role_source: RoleSource = "rule"
    role_confidence: float = 0.0
    preview_data_uri: str | None = None


# Chrome detection

@dataclass
class ChromeTextItem:
    text: str
    pages: list[int]
    page_count: int
    position_stable_chrome: bool
    bbox_norm_mean: tuple[float, float, float, float]
    bbox_norm_stddev: tuple[float, float, float, float]
    placeholder_hint: str | None
    action: ElementActionLabel


# Element actions

@dataclass
class ElementAction:
    page_type: PageType
    element_id: str
    action: ElementActionLabel
    placeholder: str | None = None
    reason: str | None = None
    source: RoleSource = "rule"


# Page classifier

@dataclass
class PageClassification:
    page_type: PageType | None
    confidence: float
    signals: dict[str, float] = field(default_factory=dict)


# Templateizer output

@dataclass(frozen=True)
class PlaceholderInstance:
    name: str
    bbox: BoundingBox
    style: dict[str, str]


@dataclass
class TemplateizeOutput:
    page_type: PageType
    svg_text: str
    placeholders: list[PlaceholderInstance]
    content_area: BoundingBox | None
    z_order_preserved: bool = True
    warnings: list["ManifestWarning"] = field(default_factory=list)


# User annotations

@dataclass
class UserAnnotation:
    annotation_id: str
    slide_index: int
    bbox_norm: BoundingBox
    note: str
    linked_element_id: str | None = None
    created_at: float = 0.0
    resolved: bool = False


# JSON-shaped persisted objects (TypedDict)

class ChatMessage(TypedDict, total=False):
    role: ChatRole
    content: str
    created_at: float


class UserAnnotationRecord(TypedDict, total=False):
    annotation_id: str
    slide_index: int
    bbox_norm: dict[str, float]
    note: str
    linked_element_id: str | None
    created_at: float
    resolved: bool


class AssetCandidateOverride(TypedDict, total=False):
    asset_id: str
    name: str
    role: AssetRole
    role_source: RoleSource


class ElementActionRecord(TypedDict, total=False):
    page_type: PageType
    element_id: str
    action: ElementActionLabel
    placeholder: str
    reason: str
    source: RoleSource


class PageSelections(TypedDict, total=False):
    cover: int | None
    toc: int | None
    chapter: int | None
    content: int | None
    ending: int | None


class PageTypeCandidates(TypedDict, total=False):
    cover: list[int]
    toc: list[int]
    chapter: list[int]
    content: list[int]
    ending: list[int]


class PlaceholderHints(TypedDict, total=False):
    cover: dict[str, str]
    toc: dict[str, str]
    chapter: dict[str, str]
    content: dict[str, str]
    ending: dict[str, str]


class StepRecord(TypedDict, total=False):
    id: str
    label: str
    status: StepStatus
    started_at: float
    ended_at: float
    duration_ms: int
    message: str
    error: str


class LLMTraceActionPlan(TypedDict, total=False):
    page_selections: PageSelections
    asset_decisions: list[dict[str, Any]]
    placeholder_decisions: list[dict[str, Any]]
    element_actions: list[ElementActionRecord]


class LLMTraceEntry(TypedDict, total=False):
    iteration: int
    updated_at: float
    input_hash: str
    input_excerpt: str
    raw_response_excerpt: str
    action_plan: LLMTraceActionPlan
    changed: bool
    retried_no_change: bool
    rule_patches: list[str]


class ReviewDraft(TypedDict, total=False):
    schema_version: int
    import_id: str
    template_id: str
    label: str
    status: TaskStatus
    export_mode: ExportMode
    slide_count: int
    page_selections: PageSelections
    page_type_candidates: PageTypeCandidates
    assets: dict[str, AssetCandidateOverride]
    assets_full: list[dict[str, Any]]
    preserve_texts: list[str]
    placeholder_hints: PlaceholderHints
    element_actions: list[ElementActionRecord]
    annotations: list[UserAnnotationRecord]
    conversation: list[ChatMessage]
    feedback_history: list[str]
    llm_trace: list[LLMTraceEntry]
    design_spec_md: str | None


class ImportTaskState(TypedDict, total=False):
    import_id: str
    status: TaskStatus
    stage: str
    progress: float
    message: str
    created_at: float
    updated_at: float
    review_required: bool
    template_id: str | None
    label: str
    source_file: str
    slide_count: int
    export_mode: ExportMode
    error: str | None
    error_kind: ErrorKind | None
    steps: list[StepRecord]
    theme_colors: list[str]


class ManifestCanvas(TypedDict, total=False):
    width: int
    height: int


class ManifestTheme(TypedDict, total=False):
    colors: dict[str, str]
    fonts: dict[str, str]


class ManifestWarning(TypedDict, total=False):
    code: ManifestWarningCode
    reason: str
    context: dict[str, Any]


class ManifestAssetEntry(TypedDict, total=False):
    asset_id: str
    file_name: str
    role: AssetRole
    pages: list[int]
    bbox_norm: dict[str, float]
    sha1: str
    bytes: int


class ManifestContentArea(TypedDict, total=False):
    x: float
    y: float
    width: float
    height: float


class TemplateManifest(TypedDict, total=False):
    schema_version: int
    template_id: str
    label: str
    source_file: str
    slide_count: int
    canvas: ManifestCanvas
    theme: ManifestTheme
    page_type_candidates: PageTypeCandidates
    page_selections: PageSelections
    common_assets: list[ManifestAssetEntry]
    content_area: ManifestContentArea | None
    warnings: list[ManifestWarning]
    imported_at: float
    export_mode: ExportMode
    importer_version: str


# Layout pack

@dataclass
class LayoutPack:
    template_id: str
    label: str
    manifest: TemplateManifest
    svgs: dict[PageType, str]
    design_spec: str
    assets: dict[str, bytes] = field(default_factory=dict)
    import_trace: list[LLMTraceEntry] = field(default_factory=list)


# Pipeline result types

@dataclass
class ImportResult:
    template_id: str = ""
    label: str = ""
    status: TaskStatus = "processing"
    stage: str = "uploaded"
    progress: float = 0.0
    message: str = ""
    steps: list[StepRecord] = field(default_factory=list)
    review_required: bool = False
    export_mode: str = ""
    slide_count: int = 0
    cover_svg: str = ""
    content_svg: str = ""
    theme_colors: list[str] = field(default_factory=list)
    error: str = ""
    error_kind: ErrorKind | None = None


@dataclass
class InstallResult:
    template_id: str
    layout_dir: Path
    already_complete: bool = False
    rolled_back: bool = False


# LLM-validated plan (Pydantic v2)

class LLMPageSelections(BaseModel):
    cover: int | None = None
    toc: int | None = None
    chapter: int | None = None
    content: int | None = None
    ending: int | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class LLMAssetDecision(BaseModel):
    asset_id: str
    role: AssetRole
    name: str | None = None
    reason: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class LLMPlaceholderDecision(BaseModel):
    page_type: PageType
    name: PlaceholderName
    text: str


class LLMElementAction(BaseModel):
    page_type: PageType
    element_id: str
    action: ElementActionLabel
    placeholder: PlaceholderName | None = None
    reason: str | None = None


class LLMTemplateImportPlan(BaseModel):
    label: str | None = None
    page_selections: LLMPageSelections = Field(default_factory=LLMPageSelections)
    asset_decisions: list[LLMAssetDecision] = Field(default_factory=list)
    placeholder_decisions: list[LLMPlaceholderDecision] = Field(default_factory=list)
    element_actions: list[LLMElementAction] = Field(default_factory=list)
    preserve_texts: list[str] = Field(default_factory=list)
    design_spec_md: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)


__all__ = [
    "PageType", "AssetRole", "AssetLayer", "ElementActionLabel",
    "RoleSource", "ExportMode", "StepStatus", "TaskStatus",
    "ErrorKind", "PlaceholderName", "ChatRole", "ManifestWarningCode",
    "TemplateImportError", "RenderError", "ExtractionError",
    "LLMPlanError", "PersistenceError",
    "BoundingBox", "SlideMetrics", "RenderResult",
    "PipelineContext", "AssetOccurrence", "AssetCandidate",
    "ChromeTextItem", "UserAnnotation", "ElementAction",
    "PageClassification", "PlaceholderInstance", "TemplateizeOutput",
    "ChatMessage", "UserAnnotationRecord", "AssetCandidateOverride",
    "ElementActionRecord", "PageSelections", "PageTypeCandidates",
    "PlaceholderHints", "StepRecord", "LLMTraceActionPlan",
    "LLMTraceEntry", "ReviewDraft", "ImportTaskState",
    "ManifestCanvas", "ManifestTheme", "ManifestWarning",
    "ManifestAssetEntry", "ManifestContentArea", "TemplateManifest",
    "LayoutPack", "ImportResult", "InstallResult",
    "LLMPageSelections", "LLMAssetDecision", "LLMPlaceholderDecision",
    "LLMElementAction", "LLMTemplateImportPlan",
]
