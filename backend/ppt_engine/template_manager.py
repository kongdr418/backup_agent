"""Template manager: loads and provides built-in PPT template context.

Templates are stored in ``assets/templates/layouts/<template_id>/``.
Each template directory contains:
- ``design_spec.md``  — design specification (colors, fonts, layout)
- ``01_cover.svg``    — cover page skeleton
- ``02_chapter.svg``  — chapter/section page skeleton
- ``03_content.svg``  — content page skeleton
- ``04_ending.svg``   — ending page skeleton
- ``02_toc.svg``      — table of contents (optional)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


_TEMPLATES_ROOT = Path(__file__).resolve().parent / "assets" / "templates" / "layouts"
_INDEX_PATH = _TEMPLATES_ROOT / "layouts_index.json"

_SVG_TEMPLATE_FIELDS = ("cover_svg", "chapter_svg", "content_svg", "ending_svg", "toc_svg")
_VIEWBOX_RE = re.compile(r'viewBox=["\']([^"\']+)["\']')


@dataclass
class TemplateInfo:
    """Lightweight descriptor for a built-in template."""

    template_id: str
    label: str = ""
    summary: str = ""
    tone: str = ""
    theme_mode: str = ""
    category: str = ""
    keywords: list[str] = field(default_factory=list)
    slide_count: int = 0
    has_cover: bool = False
    has_chapter: bool = False
    has_content: bool = False
    has_ending: bool = False
    has_toc: bool = False


@dataclass
class TemplateContent:
    """Full loaded template content."""

    info: TemplateInfo
    template_dir: Path | None = None
    viewbox: str = ""
    design_spec: str = ""
    cover_svg: str = ""
    chapter_svg: str = ""
    content_svg: str = ""
    ending_svg: str = ""
    toc_svg: str = ""
    content_area: dict[str, int] = field(default_factory=lambda: {"x": 40, "y": 100, "width": 1200, "height": 520})


def _parse_content_area_from_svg(svg_text: str) -> dict[str, int] | None:
    """Try to find a ``<g id="content-area">`` or ``{{CONTENT_AREA}}`` region."""
    m = re.search(r'<g\s+id=["\']content-area["\']\s*>', svg_text, re.IGNORECASE)
    if m:
        after = svg_text[m.end(): m.end() + 500]
        rect_m = re.search(
            r'<rect\s+[^>]*x=["\'](\d+)["\'][^>]*y=["\'](\d+)["\']'
            r'[^>]*width=["\'](\d+)["\'][^>]*height=["\'](\d+)["\']',
            after,
        )
        if rect_m:
            return {
                "x": int(rect_m.group(1)),
                "y": int(rect_m.group(2)),
                "width": int(rect_m.group(3)),
                "height": int(rect_m.group(4)),
            }
    return None


def _parse_viewbox(svg_text: str) -> str:
    match = _VIEWBOX_RE.search(svg_text or "")
    return match.group(1).strip() if match else ""


def list_templates() -> list[TemplateInfo]:
    """Return descriptors for all installed built-in templates."""
    if not _INDEX_PATH.exists():
        return []
    data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
    results: list[TemplateInfo] = []
    categories = data.get("categories", {})
    layouts = data.get("layouts", {})

    cat_map: dict[str, str] = {}
    for cat_id, cat_data in categories.items():
        for lid in cat_data.get("layouts", []):
            cat_map[lid] = cat_id

    for tid, meta in layouts.items():
        tdir = _TEMPLATES_ROOT / tid
        if not tdir.is_dir():
            continue
        results.append(
            TemplateInfo(
                template_id=tid,
                label=meta.get("label", tid),
                summary=meta.get("summary", ""),
                tone=meta.get("tone", ""),
                theme_mode=meta.get("themeMode", ""),
                category=cat_map.get(tid, ""),
                keywords=meta.get("keywords", []),
                slide_count=meta.get("slideCount", 0),
                has_cover=(tdir / "01_cover.svg").exists(),
                has_chapter=(tdir / "02_chapter.svg").exists(),
                has_content=(tdir / "03_content.svg").exists(),
                has_ending=(tdir / "04_ending.svg").exists(),
                has_toc=(tdir / "02_toc.svg").exists(),
            )
        )
    return results


def load_template(template_id: str) -> TemplateContent | None:
    """Load a template by ID. Returns *None* if not found."""
    tdir = _TEMPLATES_ROOT / template_id
    if not tdir.is_dir():
        return None

    meta: dict = {}
    if _INDEX_PATH.exists():
        data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
        meta = data.get("layouts", {}).get(template_id, {})

    info = TemplateInfo(
        template_id=template_id,
        label=meta.get("label", template_id),
        summary=meta.get("summary", ""),
        tone=meta.get("tone", ""),
        theme_mode=meta.get("themeMode", ""),
        keywords=meta.get("keywords", []),
        slide_count=meta.get("slideCount", 0),
        has_cover=(tdir / "01_cover.svg").exists(),
        has_chapter=(tdir / "02_chapter.svg").exists(),
        has_content=(tdir / "03_content.svg").exists(),
        has_ending=(tdir / "04_ending.svg").exists(),
        has_toc=(tdir / "02_toc.svg").exists(),
    )

    def _read(name: str) -> str:
        p = tdir / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    cover_svg = _read("01_cover.svg")
    chapter_svg = _read("02_chapter.svg")
    content_svg = _read("03_content.svg")
    ending_svg = _read("04_ending.svg")
    toc_svg = _read("02_toc.svg")
    content_area = _parse_content_area_from_svg(content_svg) or {
        "x": 40, "y": 100, "width": 1200, "height": 520,
    }
    viewbox = next(
        (
            parsed
            for parsed in (
                _parse_viewbox(content_svg),
                _parse_viewbox(cover_svg),
                _parse_viewbox(chapter_svg),
                _parse_viewbox(ending_svg),
                _parse_viewbox(toc_svg),
            )
            if parsed
        ),
        "",
    )

    return TemplateContent(
        info=info,
        template_dir=tdir,
        viewbox=viewbox,
        design_spec=_read("design_spec.md"),
        cover_svg=cover_svg,
        chapter_svg=chapter_svg,
        content_svg=content_svg,
        ending_svg=ending_svg,
        toc_svg=toc_svg,
        content_area=content_area,
    )


def build_template_context(tmpl: TemplateContent) -> str:
    """Build a text block for injecting into the SVG executor prompt."""
    ca = tmpl.content_area
    return (
        f"## Template Reference\n"
        f"- Template: {tmpl.info.label}\n"
        f"- Theme: {tmpl.info.theme_mode}, Tone: {tmpl.info.tone}\n"
        f"- Native viewBox: `{tmpl.viewbox}`\n"
        f"- Content area: x={ca['x']}, y={ca['y']}, "
        f"width={ca['width']}, height={ca['height']}\n"
        f"- Design spec: see template's design_spec.md\n"
        f"- All content MUST be placed within the content area boundary.\n"
        f"- Preserve the template's color scheme, typography, and layout structure.\n"
        f"- Cover/chapter/ending pages MUST follow the template SVG structure.\n"
        f"- Content pages MUST respect the content area boundary."
    )


def build_template_skeletons(tmpl: TemplateContent) -> dict[str, str]:
    """Extract page-type SVG skeletons for per-page injection."""
    skeletons: dict[str, str] = {}
    if tmpl.cover_svg:
        skeletons["cover"] = tmpl.cover_svg
    if tmpl.chapter_svg:
        skeletons["chapter"] = tmpl.chapter_svg
    if tmpl.content_svg:
        skeletons["content"] = tmpl.content_svg
    if tmpl.ending_svg:
        skeletons["ending"] = tmpl.ending_svg
    if tmpl.toc_svg:
        skeletons["toc"] = tmpl.toc_svg
    return skeletons
