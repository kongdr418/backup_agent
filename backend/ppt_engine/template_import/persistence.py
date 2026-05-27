"""Stable JSON serialization + transactional layout install.

All writes use ``json.dumps(sort_keys=True, ensure_ascii=False,
separators=(',', ':'))`` followed by a trailing newline so repeated
writes of equivalent objects produce byte-identical files. Layout install
is wrapped in a rename -> write -> drop_backup transaction with rollback
on any failure.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ppt_engine.config import settings

from .types import InstallResult, LayoutPack, PersistenceError, TemplateManifest

if TYPE_CHECKING:  # pragma: no cover
    from .types import ReviewDraft


# Canonical filename for each page type in an installed layout pack
_PAGE_TYPE_FILES: dict[str, str] = {
    "cover": "01_cover.svg",
    "toc": "02_toc.svg",
    "chapter": "02_chapter.svg",
    "content": "03_content.svg",
    "ending": "04_ending.svg",
}


def _layouts_root() -> Path:
    """Directory holding all installed layout packs."""
    return settings.templates_dir / "layouts"


# Path helpers


def _imports_root() -> Path:
    return settings.workspaces_dir / "template_imports"


def _import_dir(import_id: str) -> Path:
    return _imports_root() / import_id


def _state_path(import_id: str) -> Path:
    return _import_dir(import_id) / "state.json"


def _review_path(import_id: str) -> Path:
    return _import_dir(import_id) / "review.json"


# Stable JSON I/O


def _dumps_stable(obj: Any) -> str:
    """Canonical JSON: sorted keys, no ASCII escaping, compact, trailing newline."""
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically via tmp + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, path)


def _read_json_or_none(path: Path) -> dict[str, Any] | None:
    """Return parsed JSON dict or ``None`` if the file is absent."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(import_id: str, state: dict[str, Any]) -> None:
    _atomic_write_text(_state_path(import_id), _dumps_stable(state))


def read_state(import_id: str) -> dict[str, Any] | None:
    return _read_json_or_none(_state_path(import_id))


def write_review(import_id: str, draft: "ReviewDraft") -> None:
    _atomic_write_text(_review_path(import_id), _dumps_stable(draft))


def read_review(import_id: str) -> "ReviewDraft | None":
    data = _read_json_or_none(_review_path(import_id))
    if data is None:
        return None
    return data  # type: ignore[return-value]


def transactional_install_layout(
    template_id: str,
    pack: "LayoutPack",
) -> "InstallResult":
    """Atomically install a LayoutPack under layouts/<template_id>."""
    layouts_root = _layouts_root()
    layouts_root.mkdir(parents=True, exist_ok=True)

    target = layouts_root / template_id
    backup = layouts_root / f"{template_id}.bak"

    canonical_manifest = _dumps_stable(pack.manifest).encode("utf-8")

    # Idempotency check
    existing_manifest_path = target / "manifest.json"
    if target.exists() and existing_manifest_path.exists():
        try:
            existing_bytes = existing_manifest_path.read_bytes()
        except OSError:
            existing_bytes = b""
        if existing_bytes == canonical_manifest:
            return InstallResult(
                template_id=template_id,
                layout_dir=target,
                already_complete=True,
            )

    # Clear stale backup
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)

    backed_up = False
    if target.exists():
        shutil.move(str(target), str(backup))
        backed_up = True

    try:
        target.mkdir(parents=True, exist_ok=False)

        # Page-type SVGs
        for page_type, file_name in _PAGE_TYPE_FILES.items():
            svg_text = pack.svgs.get(page_type)
            if svg_text is None:
                continue
            (target / file_name).write_text(svg_text, encoding="utf-8")

        # design_spec.md
        (target / "design_spec.md").write_text(pack.design_spec, encoding="utf-8")

        # manifest.json
        (target / "manifest.json").write_bytes(canonical_manifest)

        # import_trace.json
        if pack.import_trace:
            (target / "import_trace.json").write_bytes(
                _dumps_stable(list(pack.import_trace)).encode("utf-8")
            )

        # assets/<file_name>
        if pack.assets:
            assets_dir = target / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            for file_name, payload in pack.assets.items():
                (assets_dir / file_name).write_bytes(payload)

    except Exception as exc:  # noqa: BLE001
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        if backed_up and backup.exists():
            try:
                shutil.move(str(backup), str(target))
            except OSError:
                pass
        raise PersistenceError(
            reason=str(exc) or exc.__class__.__name__,
            error_kind="persistence",
            context={"template_id": template_id},
        ) from exc

    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)

    return InstallResult(
        template_id=template_id,
        layout_dir=target,
        already_complete=False,
    )


def update_user_index(
    template_id: str,
    label: str,
    manifest: TemplateManifest,
) -> None:
    """Upsert a row in user_templates.json after a successful import."""
    index_path = _layouts_root() / "user_templates.json"

    existing = _read_json_or_none(index_path) or {}
    if not isinstance(existing, dict):
        existing = {}
    templates = existing.get("templates")
    if not isinstance(templates, dict):
        templates = {}

    prior_row = templates.get(template_id)
    if not isinstance(prior_row, dict):
        prior_row = {}

    slide_count = int(manifest.get("slide_count") or 0)
    imported_at_raw = manifest.get("imported_at")
    imported_at: float | None
    if isinstance(imported_at_raw, (int, float)):
        imported_at = float(imported_at_raw)
    else:
        prior_imported = prior_row.get("imported_at")
        if isinstance(prior_imported, (int, float)):
            imported_at = float(prior_imported)
        else:
            import time as _time
            imported_at = _time.time()

    summary_value = manifest.get("source_file") or template_id
    summary = f"Imported from {summary_value}"

    merged: dict[str, Any] = dict(prior_row)
    merged["label"] = label
    merged["summary"] = summary
    merged["slide_count"] = slide_count
    merged["slideCount"] = slide_count
    merged["imported_at"] = imported_at

    templates[template_id] = merged
    existing["templates"] = templates

    _atomic_write_text(index_path, _dumps_stable(existing))


def remove_user_template(template_id: str) -> bool:
    """Remove a user template from disk + index."""
    if not template_id.startswith("user_"):
        raise ValueError("built-in templates are immutable")

    found = False

    index_path = _layouts_root() / "user_templates.json"
    existing = _read_json_or_none(index_path)
    if isinstance(existing, dict):
        templates = existing.get("templates")
        if isinstance(templates, dict) and template_id in templates:
            templates.pop(template_id, None)
            existing["templates"] = templates
            _atomic_write_text(index_path, _dumps_stable(existing))
            found = True

    layout_dir = _layouts_root() / template_id
    if layout_dir.is_dir():
        shutil.rmtree(layout_dir, ignore_errors=True)
        found = True

    return found


def rename_user_template(template_id: str, label: str) -> bool:
    """Rename a user template by mutating only the index label field."""
    if not template_id.startswith("user_"):
        raise ValueError("built-in templates are immutable")

    index_path = _layouts_root() / "user_templates.json"
    existing = _read_json_or_none(index_path)
    if not isinstance(existing, dict):
        return False

    templates = existing.get("templates")
    if not isinstance(templates, dict):
        return False

    row = templates.get(template_id)
    if not isinstance(row, dict):
        return False

    new_label = label.strip() or template_id
    if row.get("label") == new_label:
        return True

    row["label"] = new_label
    templates[template_id] = row
    existing["templates"] = templates

    _atomic_write_text(index_path, _dumps_stable(existing))
    return True


# v1 -> v2 in-memory upgrade & layout-pack loading


def upgrade_v1_to_v2_in_memory(manifest: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a v1 manifest dict in-memory to v2 schema."""
    if not isinstance(manifest, dict):
        return {"schema_version": 2, "content_area": None, "warnings": [], "common_assets": []}
    if manifest.get("schema_version") == 2:
        return manifest
    upgraded: dict[str, Any] = dict(manifest)
    upgraded["schema_version"] = 2
    upgraded.setdefault("content_area", None)
    upgraded.setdefault("warnings", [])
    upgraded.setdefault("common_assets", [])
    return upgraded


def load_template_pack(template_id: str) -> "LayoutPack | None":
    """Read an installed layout pack from disk."""
    target = _layouts_root() / template_id
    if not target.is_dir():
        return None

    svgs: dict[str, str] = {}
    for page_type, file_name in _PAGE_TYPE_FILES.items():
        path = target / file_name
        if path.exists():
            try:
                svgs[page_type] = path.read_text(encoding="utf-8")
            except OSError:
                continue

    design_spec_path = target / "design_spec.md"
    design_spec = ""
    if design_spec_path.exists():
        try:
            design_spec = design_spec_path.read_text(encoding="utf-8")
        except OSError:
            design_spec = ""

    manifest_path = target / "manifest.json"
    manifest_raw: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8")) or {}
        except (OSError, json.JSONDecodeError):
            manifest_raw = {}
    manifest = upgrade_v1_to_v2_in_memory(manifest_raw)

    trace_path = target / "import_trace.json"
    import_trace: list[Any] = []
    if trace_path.exists():
        try:
            loaded = json.loads(trace_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                import_trace = loaded
        except (OSError, json.JSONDecodeError):
            import_trace = []

    assets: dict[str, bytes] = {}
    assets_dir = target / "assets"
    if assets_dir.is_dir():
        for child in assets_dir.iterdir():
            if child.is_file():
                try:
                    assets[child.name] = child.read_bytes()
                except OSError:
                    continue

    label = str(manifest.get("label") or template_id)
    return LayoutPack(
        template_id=template_id,
        label=label,
        manifest=manifest,  # type: ignore[arg-type]
        svgs=svgs,  # type: ignore[arg-type]
        design_spec=design_spec,
        assets=assets,
        import_trace=import_trace,
    )
