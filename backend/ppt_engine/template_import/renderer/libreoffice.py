"""LibreOffice headless renderer (cross-platform fallback path).

Invokes ``soffice --headless --convert-to svg --outdir <out> <pptx>``,
then normalizes the LibreOffice file naming
(``<stem>.svg, <stem>-1.svg, …``) into ``slide-001.svg`` ordering.
Handles the case where some LibreOffice builds emit a single combined
SVG for multi-page decks by splitting it into per-slide files.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from ..types import RenderError


_TIMEOUT_SECONDS = 120

# Regex patterns for combined SVG detection and splitting
_SLIDE_COUNT_RE = re.compile(r'ooo:number-of-slides="(\d+)"')
_SVG_TAG_RE = re.compile(r'(<svg\b[^>]*>)', re.IGNORECASE)
_CLIPPATH_DEFS_RE = re.compile(
    r'(<defs\s+class="ClipPathGroup">[\s\S]*?</defs>)', re.IGNORECASE
)
_FONT_DEFS_RE = re.compile(
    r'(<defs>\s*<font\s+id="EmbeddedFont_\d+"[^>]*>[\s\S]*?</font>\s*</defs>)',
    re.IGNORECASE,
)
_SLIDEGROUP_RE = re.compile(
    r'<g\s+class="SlideGroup">', re.IGNORECASE
)
_CONTAINER_RE = re.compile(
    r'<g\s+id="container-id\d+">', re.IGNORECASE
)
_VIS_G_RE = re.compile(
    r'<g\s+visibility="[^"]*">\s*$', re.MULTILINE
)


def _split_combined_svg(svg_path: Path, out_dir: Path) -> list[Path]:
    """Split a combined LibreOffice SVG into per-slide files.

    Some LibreOffice builds export all slides as a single horizontally-
    tiled SVG. This function detects the ``ooo:number-of-slides``
    metadata, extracts each slide's ``<g class="Slide">`` container,
    and writes individual ``slide-NNN.svg`` files with the correct
    per-slide ``viewBox``.

    Returns the list of split SVG paths, or ``[svg_path]`` unchanged
    if the file is not a combined SVG.
    """
    try:
        text = svg_path.read_text(encoding="utf-8")
    except OSError:
        return [svg_path]

    count_match = _SLIDE_COUNT_RE.search(text)
    if not count_match:
        return [svg_path]
    slide_count = int(count_match.group(1))
    if slide_count <= 1:
        return [svg_path]

    # Extract SVG root tag
    svg_tag_match = _SVG_TAG_RE.search(text)
    if not svg_tag_match:
        return [svg_path]
    svg_tag = svg_tag_match.group(1)

    # Parse viewBox to compute per-slide dimensions
    vb_match = re.search(r'viewBox="([^"]*)"', svg_tag)
    if not vb_match:
        return [svg_path]
    vb_parts = vb_match.group(1).split()
    if len(vb_parts) != 4:
        return [svg_path]
    total_w = float(vb_parts[2])
    total_h = float(vb_parts[3])
    page_w = total_w / slide_count

    # Extract clip path defs
    clip_match = _CLIPPATH_DEFS_RE.search(text)
    clip_defs = clip_match.group(1) if clip_match else ""

    # Extract embedded font defs
    font_blocks = _FONT_DEFS_RE.findall(text)
    font_defs = "\n".join(font_blocks)

    # Find the SlideGroup boundaries
    sg_match = _SLIDEGROUP_RE.search(text)
    if not sg_match:
        return [svg_path]
    sg_start = sg_match.end()  # right after <g class="SlideGroup">

    # Find all <g visibility="hidden"> within the SlideGroup — each wraps one slide
    vis_pattern = re.compile(r'<g\s+visibility="hidden">', re.IGNORECASE)
    vis_matches = list(vis_pattern.finditer(text, sg_start))
    if len(vis_matches) < slide_count:
        return [svg_path]

    # Find the closing </g> of SlideGroup (match nesting depth from sg_start)
    depth = 1
    sg_end = sg_start
    pos = sg_start
    while depth > 0 and pos < len(text):
        open_m = re.search(r'<g\b', text[pos:], re.IGNORECASE)
        close_m = re.search(r'</g>', text[pos:], re.IGNORECASE)
        if not close_m:
            break
        if open_m and open_m.start() < close_m.start():
            depth += 1
            pos += open_m.end()
        else:
            depth -= 1
            if depth == 0:
                sg_end = pos + close_m.start()
            pos += close_m.end()

    # Extract each slide: from vis_matches[i] to vis_matches[i+1] (or sg_end)
    slides_raw: list[str] = []
    for i in range(slide_count):
        start = vis_matches[i].start()
        if i + 1 < len(vis_matches):
            end = vis_matches[i + 1].start()
        else:
            end = sg_end
        slides_raw.append(text[start:end].strip())

    if len(slides_raw) != slide_count:
        return [svg_path]

    # Write per-slide SVG files
    svg_tag_single = re.sub(
        r'viewBox="[^"]*"',
        f'viewBox="0 0 {page_w:.0f} {total_h:.0f}"',
        svg_tag,
    )
    # Also fix width/height if present (but not stroke-width, font-size etc.)
    svg_tag_single = re.sub(
        r'(?<!\w-)width="[^"]*"', f'width="{page_w:.0f}"', svg_tag_single
    )
    svg_tag_single = re.sub(
        r'(?<!\w-)height="[^"]*"', f'height="{total_h:.0f}"', svg_tag_single
    )

    # Update clip path rect to match single-page viewBox
    clip_single = re.sub(
        r'width="[^"]*"\s+height="[^"]*"',
        f'width="{page_w:.0f}" height="{total_h:.0f}"',
        clip_defs,
    )
    # Also fix the shrink clip rect offset
    clip_single = re.sub(
        r'<rect\s+x="[^"]*"\s+y="[^"]*"\s+width="[^"]*"\s+height="[^"]*"',
        f'<rect x="0" y="0" width="{page_w:.0f}" height="{total_h:.0f}"',
        clip_single,
        count=1,
    )

    out_files: list[Path] = []
    for i, slide_content in enumerate(slides_raw):
        slide_vb_x = i * page_w
        slide_tag = re.sub(
            r'viewBox="[^"]*"',
            f'viewBox="{slide_vb_x:.0f} 0 {page_w:.0f} {total_h:.0f}"',
            svg_tag,
        )
        slide_tag = re.sub(
            r'(?<!\w-)width="[^"]*"', f'width="{page_w:.0f}"', slide_tag
        )
        slide_tag = re.sub(
            r'(?<!\w-)height="[^"]*"', f'height="{total_h:.0f}"', slide_tag
        )

        slide_svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'{slide_tag}\n'
            f'{clip_single}\n'
            f'{font_defs}\n'
            f'{slide_content}\n'
            '</svg>\n'
        )

        # Write to temp name first to avoid overwriting the source file
        tmp = out_dir / f".__split_slide_{i + 1:03d}.svg"
        tmp.write_text(slide_svg, encoding="utf-8")
        out_files.append(tmp)

    # Remove the original combined SVG
    try:
        svg_path.unlink()
    except OSError:
        pass

    # Rename temp files to final names
    final: list[Path] = []
    for i, tmp in enumerate(out_files):
        target = out_dir / f"slide-{i + 1:03d}.svg"
        if target.exists():
            target.unlink()
        tmp.rename(target)
        final.append(target)

    return final


def _resolve_soffice() -> str | None:
    """Locate the ``soffice`` binary via env override or ``PATH``."""
    override = os.environ.get("LIBREOFFICE_BIN")
    if override:
        if Path(override).exists():
            return override
        # Also accept a bare command on PATH (e.g. "soffice").
        on_path = shutil.which(override)
        if on_path:
            return on_path
    return shutil.which("soffice")


def _render_via_libreoffice(pptx: Path, out_dir: Path) -> list[Path]:
    """Convert ``pptx`` to per-slide SVG files via LibreOffice headless.

    Returns the renamed slide files in slide order. Raises
    :class:`RenderError` (``error_kind="render"``) when ``soffice`` is
    missing, exits non-zero, times out, or produces no output.
    """
    pptx = Path(pptx)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    soffice = _resolve_soffice()
    if not soffice:
        raise RenderError("soffice not found", error_kind="render")

    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        "svg",
        "--outdir",
        str(out_dir),
        str(pptx),
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError(
            f"LibreOffice export timed out after {_TIMEOUT_SECONDS}s",
            error_kind="render",
        ) from exc
    except OSError as exc:
        raise RenderError(
            f"LibreOffice invocation failed: {exc}",
            error_kind="render",
        ) from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RenderError(
            f"LibreOffice export failed: {stderr or 'non-zero exit'}",
            error_kind="render",
        )

    files = _normalize_libreoffice_filenames(out_dir, pptx.stem)

    # Handle combined SVG: some LibreOffice builds emit one merged SVG
    # for multi-page decks — split it into per-slide files.
    if len(files) == 1:
        split = _split_combined_svg(files[0], out_dir)
        if len(split) > 1:
            files = split

    if not files:
        stderr = (completed.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RenderError(
            f"LibreOffice export produced no SVG files: {stderr or 'unknown'}",
            error_kind="render",
        )
    return files


def _normalize_libreoffice_filenames(out_dir: Path, stem: str) -> list[Path]:
    """Rename ``<stem>.svg, <stem>-1.svg, …`` → ``slide-001.svg, ...``.

    Some LibreOffice builds emit a single ``<stem>.svg`` for multi-page
    decks (one combined SVG); others emit one file per slide with the
    suffix scheme ``<stem>.svg`` (slide 1) plus ``<stem>-N.svg`` for the
    remainder. Both layouts are normalized into a contiguous
    ``slide-001.svg`` sequence in slide order.
    """
    out_dir = Path(out_dir)
    base = out_dir / f"{stem}.svg"
    pattern = re.compile(re.escape(stem) + r"-(\d+)\.svg$")

    suffixed: list[tuple[int, Path]] = []
    for path in out_dir.iterdir():
        if not path.is_file():
            continue
        match = pattern.match(path.name)
        if match:
            suffixed.append((int(match.group(1)), path))
    suffixed.sort(key=lambda item: item[0])

    ordered: list[Path] = []
    if base.exists():
        ordered.append(base)
    ordered.extend(path for _, path in suffixed)

    if not ordered:
        return []

    # Rename to canonical ``slide-NNN.svg`` via a two-phase shuffle so we
    # never collide with an existing source file mid-rename.
    renamed: list[Path] = []
    for index, source in enumerate(ordered, start=1):
        tmp = out_dir / f".__pending_slide_{index:03d}.svg"
        if tmp.exists():
            tmp.unlink()
        source.rename(tmp)
        renamed.append(tmp)

    final: list[Path] = []
    for index, tmp in enumerate(renamed, start=1):
        target = out_dir / f"slide-{index:03d}.svg"
        if target.exists():
            target.unlink()
        tmp.rename(target)
        final.append(target)
    return final


__all__ = ["_render_via_libreoffice", "_normalize_libreoffice_filenames"]
