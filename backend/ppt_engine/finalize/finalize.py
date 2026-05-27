"""Unified SVG post-processing pipeline.

Orchestrates all finalization steps in sequence:
1. Repair malformed SVG
2. Embed icons
3. Crop images (preserveAspectRatio="slice")
4. Fix image aspect ratios
5. Embed external images as Base64
6. Flatten tspan text elements
7. Merge adjacent text elements
8. Reflow text (icon-text alignment)
9. Normalize fonts
10. Convert rounded rects to paths
"""

from __future__ import annotations

from pathlib import Path

from ppt_engine.config import settings

from .crop_images import crop_images_in_svg
from .embed_icons import embed_icons_in_file
from .embed_images import build_image_index, embed_images_in_svg
from .fix_image_aspect import fix_image_aspect_in_svg
from .flatten_tspan import flatten_text_in_svg
from .merge_adjacent_text import merge_adjacent_text_in_svg
from .normalize_fonts import normalize_text_fonts_in_svg
from .svg_text_reflow import reflow_text_in_svg
from .repair_svg import repair_svg_file
from .svg_rect_to_path import convert_rounded_rects_in_svg
# TODO: project_manager removed - caller passes paths directly
# from ..project_manager import prepare_for_finalize, get_svg_files


def finalize_svg_dir(
    svg_dir: Path,
    output_dir: Path | None = None,
    icons_dir: Path | None = None,
    compress: bool = False,
    max_dimension: int | None = None,
) -> dict[str, int]:
    """Run the complete SVG finalization pipeline on a directory of SVGs.

    Args:
        svg_dir: Directory containing SVG files.
        output_dir: Output directory for finalized SVGs (defaults to svg_dir).
        icons_dir: Icons directory (defaults to settings.icons_dir).
        compress: Whether to compress embedded images.
        max_dimension: Max pixel dimension for images.

    Returns:
        Dict with counts of modifications per step.
    """
    if icons_dir is None:
        icons_dir = settings.icons_dir

    if output_dir is None:
        output_dir = svg_dir
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    svg_files = sorted(svg_dir.glob("*.svg"))
    if not svg_files:
        return {"total_files": 0}

    # If output_dir differs from svg_dir, copy SVGs there first
    import shutil
    if output_dir != svg_dir:
        for f in svg_files:
            shutil.copy2(f, output_dir / f.name)
        svg_files = sorted(output_dir.glob("*.svg"))

    # Build image index relative to the parent of svg_dir
    image_index = build_image_index(svg_dir.parent)

    stats = {
        "total_files": len(svg_files),
        "svgs_repaired": 0,
        "icons_embedded": 0,
        "images_cropped": 0,
        "aspects_fixed": 0,
        "images_embedded": 0,
        "texts_flattened": 0,
        "texts_merged": 0,
        "texts_reflowed": 0,
        "fonts_normalized": 0,
        "rects_converted": 0,
    }

    for svg_path in svg_files:
        stats["svgs_repaired"] += repair_svg_file(svg_path)
        stats["icons_embedded"] += embed_icons_in_file(svg_path, icons_dir)
        stats["images_cropped"] += crop_images_in_svg(svg_path)
        stats["aspects_fixed"] += fix_image_aspect_in_svg(svg_path)
        stats["images_embedded"] += embed_images_in_svg(
            svg_path, compress=compress, max_dimension=max_dimension, image_index=image_index,
        )
        stats["texts_flattened"] += flatten_text_in_svg(svg_path)
        stats["texts_merged"] += merge_adjacent_text_in_svg(svg_path)
        stats["texts_reflowed"] += reflow_text_in_svg(svg_path)
        stats["fonts_normalized"] += normalize_text_fonts_in_svg(svg_path)
        stats["rects_converted"] += convert_rounded_rects_in_svg(svg_path)

    return stats
