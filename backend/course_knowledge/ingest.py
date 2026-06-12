from __future__ import annotations

import io
import logging
import os
import re
import uuid
import zipfile
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime
from hashlib import sha1
from typing import Any
from xml.etree import ElementTree

from .schema import CourseCatalog, KnowledgeChunk, KnowledgeDocument
from .storage import CourseKnowledgeStorage


logger = logging.getLogger(__name__)

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
SHEET_NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

COURSE_NAME_LABELS = {"\u8bfe\u7a0b\u540d\u79f0", "\u8bfe\u7a0b\u540d"}
SUMMARY_LABELS = {
    "\u8bfe\u7a0b\u7b80\u4ecb",
    "\u8bfe\u7a0b\u76ee\u6807",
    "\u8bfe\u7a0b\u8bf4\u660e",
}
MODULE_PREFIXES = (
    "\u6a21\u5757",
    "\u5355\u5143",
    "\u4e13\u9898",
)
LESSON_PREFIXES = (
    "\u8bfe\u65f6",
    "\u8bfe\u6b21",
    "\u8bfe\u7a0b",
)
KNOWLEDGE_POINT_LABELS = {
    "\u77e5\u8bc6\u70b9",
    "\u91cd\u70b9",
    "\u6838\u5fc3\u77e5\u8bc6\u70b9",
}
DEFAULT_MODULE_TITLE = "\u672a\u5206\u6a21\u5757"

# Labels that may appear on their own line with the value on the next line
_TWO_LINE_LABELS = (
    COURSE_NAME_LABELS | SUMMARY_LABELS
    | {"\u8bfe\u7a0b\u7c7b\u522b", "\u8bfe\u7a0b\u6027\u8d28", "\u8bfe\u7a0b\u5c5e\u6027",
       "\u8bfe\u7a0b\u82f1\u6587\u540d\u79f0", "\u8bfe\u7a0b\u7f16\u7801", "\u9002\u7528\u4e13\u4e1a",
       "\u8003\u6838\u65b9\u5f0f", "\u5148\u4fee\u8bfe\u7a0b", "\u603b\u5b66\u65f6", "\u5b66\u5206",
       "\u7406\u8bba\u5b66\u65f6", "\u5f00\u8bfe\u5355\u4f4d"}
)

# Content sub-fields that follow a module/lesson and contain knowledge points
_CONTENT_FIELD_LABELS = {
    "\u4e3b\u8981\u6559\u5b66\u5185\u5bb9",
    "\u91cd\u70b9",
    "\u96be\u70b9",
    "\u601d\u653f\u5143\u7d20",
}

# Numbered item: "1. xxx" (requires space after dot to avoid ref codes like "5.2\u30014.1")
_NUMBERED_ITEM_RE = re.compile(r"^\d+[\.\u3001.]\s+(.+)$")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_stem(name: str) -> str:
    stem = os.path.splitext(os.path.basename(name))[0].strip()
    return stem or "document"


def _normalize_label(text: str) -> str:
    return re.sub(r"[\s:：\-（）()]+", "", text).strip()


def _split_label_value(text: str) -> tuple[str, str]:
    matched = re.match(r"^\s*([^:：]+?)\s*[:：]\s*(.+?)\s*$", text)
    if not matched:
        return "", ""
    return matched.group(1).strip(), matched.group(2).strip()


def _tokenize_points(text: str) -> list[str]:
    values = []
    for token in re.split(r"[,，、;；/\n]+", text):
        normalized = token.strip(" \t:-：,，;；")
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def _course_hash(*parts: str) -> str:
    joined = "||".join(parts)
    return sha1(joined.encode("utf-8")).hexdigest()[:10]


class CourseKnowledgeIngestor:
    def __init__(
        self,
        backend_dir: str,
        storage: CourseKnowledgeStorage | None = None,
        now_provider: Callable[[], str] | None = None,
        vector_index: Any | None = None,
    ) -> None:
        self.backend_dir = backend_dir
        self.storage = storage or CourseKnowledgeStorage(backend_dir, now_provider=now_provider)
        self.now_provider = now_provider or _now_iso
        self.vector_index = vector_index

    def _sync_vector_index(
        self,
        user_id: str,
        course_id: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        if self.vector_index is None:
            return
        try:
            if chunks:
                self.vector_index.rebuild(user_id, course_id, chunks)
            else:
                self.vector_index.delete(user_id, course_id)
        except Exception as exc:
            logger.warning(
                "[BGE] index_sync_failed course_id=%s "
                "fallback=keyword error=%s",
                course_id,
                type(exc).__name__,
            )

    def ingest_upload(
        self,
        user_id: str,
        filename: str,
        stream: io.BytesIO | Any,
        content_type: str = "",
    ) -> dict[str, Any]:
        doc_kind = self._detect_doc_kind(filename, content_type)
        binary = stream.read()
        if not binary:
            raise ValueError("file is empty")

        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        course_payload = self._parse_payload(doc_kind, filename, binary)
        course_id = self._resolve_course_id(user_id, course_payload["course_name"])
        stored_path = self._save_original_file(user_id, document_id, filename, binary)

        document = KnowledgeDocument(
            document_id=document_id,
            user_id=user_id,
            course_id=course_id,
            title=course_payload["title"],
            source_type="upload",
            doc_kind=doc_kind,
            mime_type=content_type or self._guess_mime(filename),
            original_filename=os.path.basename(filename),
            stored_path=stored_path,
            parse_status="ready",
            created_at=self.now_provider(),
            updated_at=self.now_provider(),
        ).to_dict()
        parsed = {
            "document_id": document_id,
            "doc_kind": doc_kind,
            "course_id": course_id,
            **course_payload,
        }
        try:
            self.storage.save_document(user_id, document_id, document, parsed)
            aggregate = self._rebuild_course_indexes(user_id, course_id)
        except Exception:
            self.storage.delete_document(user_id, document_id)
            raise
        return {
            "document": document,
            "parsed": parsed,
            "catalog": aggregate["catalog"],
            "chunks": aggregate["chunks"],
            "course_map": aggregate["course_map"],
        }

    def delete_document(self, user_id: str, document_id: str) -> dict[str, Any]:
        loaded = self.storage.load_document(user_id, document_id)
        if loaded is None:
            raise ValueError("document not found")
        course_id = (loaded.get("document") or {}).get("course_id", "")
        self.storage.delete_document(user_id, document_id)
        if course_id:
            self._rebuild_course_indexes(user_id, course_id)
        return {"document_id": document_id, "course_id": course_id}

    def list_documents(self, user_id: str) -> list[dict[str, Any]]:
        rows = []
        for row in self.storage.list_documents(user_id):
            document = row.get("document") or {}
            parsed = row.get("parsed") or {}
            rows.append(
                {
                    **document,
                    "course_name": parsed.get("course_name", ""),
                    "summary": parsed.get("summary", ""),
                    "module_count": len(parsed.get("modules", []) or []),
                    "lesson_count": len(parsed.get("lessons", []) or []),
                    "knowledge_point_count": len(parsed.get("knowledge_points", []) or []),
                }
            )
        return rows

    def list_courses(self, user_id: str) -> list[dict[str, Any]]:
        return list((self.storage.load_course_map(user_id) or {}).get("courses", []))

    def _detect_doc_kind(self, filename: str, content_type: str) -> str:
        extension = os.path.splitext(filename)[1].lower()
        if extension == ".docx" or content_type == DOCX_MIME:
            return "syllabus"
        if extension == ".xlsx" or content_type == XLSX_MIME:
            return "schedule"
        raise ValueError("unsupported file type")

    def _guess_mime(self, filename: str) -> str:
        extension = os.path.splitext(filename)[1].lower()
        if extension == ".docx":
            return DOCX_MIME
        if extension == ".xlsx":
            return XLSX_MIME
        return "application/octet-stream"

    def _save_original_file(
        self,
        user_id: str,
        document_id: str,
        filename: str,
        binary: bytes,
    ) -> str:
        extension = os.path.splitext(filename)[1].lower() or ".bin"
        directory = self.storage.document_dir(user_id, document_id)
        absolute_path = os.path.join(directory, f"source{extension}")
        with open(absolute_path, "wb") as file:
            file.write(binary)
        return os.path.relpath(absolute_path, self.backend_dir).replace("\\", "/")

    def _resolve_course_id(self, user_id: str, course_name: str) -> str:
        course_map = self.storage.load_course_map(user_id)
        for course in course_map.get("courses", []):
            if (course.get("course_name") or "").strip() == course_name.strip():
                return str(course.get("course_id", ""))
        return f"course_{_course_hash(user_id, course_name)}"

    def _parse_payload(self, doc_kind: str, filename: str, binary: bytes) -> dict[str, Any]:
        if doc_kind == "syllabus":
            return self._parse_docx(filename, binary)
        if doc_kind == "schedule":
            return self._parse_xlsx(filename, binary)
        raise ValueError("unsupported file type")

    def _parse_docx(self, filename: str, binary: bytes) -> dict[str, Any]:
        raw_paragraphs = self._read_docx_paragraphs(binary)
        paragraphs = self._merge_label_value_lines(raw_paragraphs)

        course_name = ""
        summary = ""
        modules: list[dict[str, Any]] = []
        lessons: list[dict[str, Any]] = []
        knowledge_points: list[str] = []
        current_module: dict[str, Any] | None = None
        current_lesson: dict[str, Any] | None = None
        current_section: str = ""  # "theory" / "practice" / ""
        in_teaching_content = False  # True after entering 四、课程主要教学内容
        next_line_is_summary = False  # True after seeing "二、课程简介" header

        for line in paragraphs:
            if not line:
                continue

            # 0) capture summary from line after section header
            if next_line_is_summary and not summary:
                summary = line
                next_line_is_summary = False
                continue

            # 1) label:value on single line (existing logic, unchanged)
            label, value = _split_label_value(line)
            normalized_label = _normalize_label(label)
            if not course_name and normalized_label in COURSE_NAME_LABELS and value:
                course_name = value
                continue
            if not summary and normalized_label in SUMMARY_LABELS and value:
                summary = value
                continue

            # 2) detect entry into teaching content section
            norm_line = _normalize_label(line)
            if not in_teaching_content and "教学内容" in norm_line:
                in_teaching_content = True
            # section headers: (一)理论教学 / (二)实践教学
            if "理论" in norm_line and "教学" in norm_line:
                current_section = "theory"
                in_teaching_content = True
                continue
            if "实践" in norm_line and "教学" in norm_line:
                current_section = "practice"
                in_teaching_content = True
                continue
            # Major section dividers: 五、六、七、... exit teaching content
            major_match = re.match(r"^([一二三四五六七八九十]+)、(.+)", line)
            if major_match:
                section_num = "一二三四五六七八九十".index(major_match.group(1)) + 1
                if section_num >= 5:
                    in_teaching_content = False
                # Detect "二、课程简介" → next line is summary text
                section_body = _normalize_label(major_match.group(2))
                if not summary and "简介" in section_body:
                    next_line_is_summary = True
                continue

            # 3) existing prefix matching: 模块X：xxx / 课时X：xxx
            module_title = self._extract_titled_value(line, MODULE_PREFIXES)
            if module_title:
                current_module = {
                    "module_id": f"mod_{_course_hash(module_title)}",
                    "title": module_title,
                    "lessons": [],
                }
                modules.append(current_module)
                current_lesson = None
                continue

            lesson_title = self._extract_titled_value(line, LESSON_PREFIXES)
            if lesson_title:
                if current_module is None:
                    current_module = {
                        "module_id": f"mod_{_course_hash('default')}",
                        "title": DEFAULT_MODULE_TITLE,
                        "lessons": [],
                    }
                    modules.append(current_module)
                current_lesson = {
                    "lesson_id": f"lesson_{_course_hash(lesson_title)}",
                    "title": lesson_title,
                    "knowledge_points": [],
                }
                current_module["lessons"].append(current_lesson)
                lessons.append(current_lesson)
                continue

            # 4) explicit 知识点 label (existing logic)
            if normalized_label in KNOWLEDGE_POINT_LABELS and value:
                points = _tokenize_points(value)
                for point in points:
                    if point not in knowledge_points:
                        knowledge_points.append(point)
                if current_lesson is not None:
                    for point in points:
                        if point not in current_lesson["knowledge_points"]:
                            current_lesson["knowledge_points"].append(point)
                continue

            # 5) practice project type markers: 上机 / 综合 / 设计
            if current_section == "practice" and line in ("上机", "综合", "设计"):
                current_section = "practice_name_next"
                continue
            if current_section == "practice_name_next":
                # This line is the project name after a type marker
                project_name = line.strip()
                # Skip filler/requirement lines that aren't project names
                if project_name and not project_name.startswith(
                    ("课前", "课后", "当前", "合计", "验证", "设计")
                ):
                    practice_module = self._ensure_practice_module(modules)
                    current_lesson = {
                        "lesson_id": f"lesson_{_course_hash(project_name)}",
                        "title": project_name,
                        "knowledge_points": [],
                    }
                    practice_module["lessons"].append(current_lesson)
                    lessons.append(current_lesson)
                current_section = "practice"
                continue

            # 6) numbered items: "1. Python 与数据处理基础建立" (theory only)
            # Only match after entering the teaching content section, and require
            # a space after the dot to filter out reference codes like "5.2、4.1"
            if in_teaching_content and current_section in ("theory", ""):
                numbered_match = _NUMBERED_ITEM_RE.match(line)
                if numbered_match:
                    item_title = numbered_match.group(1).strip()
                    # Real module titles: >4 chars, contain Chinese, not ref codes
                    if (
                        len(item_title) > 4
                        and re.search(r"[一-鿿]", item_title)
                        and not re.match(r"^[\d\.、]+[、\.]", item_title)
                    ):
                        current_module = {
                            "module_id": f"mod_{_course_hash(item_title)}",
                            "title": item_title,
                            "lessons": [],
                        }
                        modules.append(current_module)
                        current_lesson = None
                        continue

            # 7) content sub-fields following a module/lesson
            if current_lesson is not None and value:
                content_label = normalized_label
                if any(
                    content_label.startswith(_normalize_label(cl))
                    for cl in _CONTENT_FIELD_LABELS
                ):
                    points = _tokenize_points(value)
                    for point in points:
                        if point not in knowledge_points:
                            knowledge_points.append(point)
                        if point not in current_lesson["knowledge_points"]:
                            current_lesson["knowledge_points"].append(point)
                    continue

        if not course_name:
            course_name = _safe_stem(filename)

        return {
            "title": course_name,
            "course_name": course_name,
            "summary": summary,
            "modules": modules,
            "lessons": [
                {
                    "lesson_id": lesson["lesson_id"],
                    "title": lesson["title"],
                    "knowledge_points": list(lesson["knowledge_points"]),
                }
                for lesson in lessons
            ],
            "knowledge_points": knowledge_points,
            "paragraphs": raw_paragraphs,
        }

    def _ensure_practice_module(
        self, modules: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Find or create a single '实践教学' module for practice projects."""
        for mod in modules:
            if mod["title"] == "实践教学":
                return mod
        practice_module: dict[str, Any] = {
            "module_id": f"mod_{_course_hash('实践教学')}",
            "title": "实践教学",
            "lessons": [],
        }
        modules.append(practice_module)
        return practice_module

    def _merge_label_value_lines(self, paragraphs: list[str]) -> list[str]:
        """Join orphan label lines with their value on the next line.

        E.g. ["课程名称", "人工智能与Python程序设计"] → ["课程名称：人工智能与Python程序设计"]
        """
        merged: list[str] = []
        i = 0
        while i < len(paragraphs):
            line = paragraphs[i].strip()
            if not line:
                i += 1
                continue
            # If this line looks like an orphan label (no colon, matches known labels)
            if ":" not in line and "：" not in line:
                normalized = _normalize_label(line)
                is_known_label = any(
                    normalized == _normalize_label(lbl) for lbl in _TWO_LINE_LABELS
                )
                if is_known_label and i + 1 < len(paragraphs):
                    next_line = paragraphs[i + 1].strip()
                    if next_line:
                        # Check the next line isn't itself a known label
                        next_normalized = _normalize_label(next_line)
                        next_is_label = any(
                            next_normalized == _normalize_label(lbl)
                            for lbl in _TWO_LINE_LABELS
                        )
                        if not next_is_label:
                            merged.append(f"{line}：{next_line}")
                            i += 2
                            continue
            merged.append(line)
            i += 1
        return merged

    def _parse_xlsx(self, filename: str, binary: bytes) -> dict[str, Any]:
        rows = self._read_xlsx_rows(binary)
        course_name = ""
        data_rows: list[dict[str, Any]] = []
        modules_map: OrderedDict[str, dict[str, Any]] = OrderedDict()
        lesson_map: OrderedDict[str, dict[str, Any]] = OrderedDict()
        knowledge_points: list[str] = []
        header_map: dict[str, int] | None = None

        for row in rows:
            if self._is_course_name_row(row) and not course_name:
                course_name = row[1].strip()
                continue

            detected_header_map = self._build_schedule_header_map(row)
            if detected_header_map:
                header_map = detected_header_map
                continue
            if not header_map:
                continue

            week = self._cell_value(row, header_map.get("week"))
            module_title = self._cell_value(row, header_map.get("module"))
            lesson_title = self._cell_value(row, header_map.get("lesson"))
            points = _tokenize_points(self._cell_value(row, header_map.get("knowledge_points")))
            if not week and not module_title and not lesson_title and not points:
                continue

            data_rows.append(
                {
                    "week": week,
                    "module": module_title,
                    "lesson": lesson_title,
                    "knowledge_points": points,
                }
            )

            if module_title and module_title not in modules_map:
                modules_map[module_title] = {
                    "module_id": f"mod_{_course_hash(module_title)}",
                    "title": module_title,
                    "lessons": [],
                }
            if lesson_title and lesson_title not in lesson_map:
                lesson_map[lesson_title] = {
                    "lesson_id": f"lesson_{_course_hash(lesson_title)}",
                    "title": lesson_title,
                    "knowledge_points": points,
                }
            if module_title and lesson_title:
                existing_titles = {item["title"] for item in modules_map[module_title]["lessons"]}
                if lesson_title not in existing_titles:
                    modules_map[module_title]["lessons"].append(lesson_map[lesson_title])
            for point in points:
                if point not in knowledge_points:
                    knowledge_points.append(point)

        if not course_name:
            course_name = _safe_stem(filename)

        return {
            "title": course_name,
            "course_name": course_name,
            "summary": "",
            "modules": list(modules_map.values()),
            "lessons": list(lesson_map.values()),
            "knowledge_points": knowledge_points,
            "rows": data_rows,
        }

    def _is_course_name_row(self, row: list[str]) -> bool:
        if len(row) < 2:
            return False
        return _normalize_label(row[0]) in COURSE_NAME_LABELS and bool(row[1].strip())

    def _build_schedule_header_map(self, row: list[str]) -> dict[str, int] | None:
        normalized = [_normalize_label(cell) for cell in row]
        aliases = {
            "week": {
                "\u5468\u6b21",
                "\u6559\u5b66\u5468\u6b21",
                "\u5468\u6570",
            },
            "module": {
                "\u6a21\u5757",
                "\u6559\u5b66\u6a21\u5757",
                "\u5355\u5143",
                "\u7ae0\u8282\u6a21\u5757",
            },
            "lesson": {
                "\u6559\u5b66\u5185\u5bb9",
                "\u8bfe\u7a0b\u5185\u5bb9",
                "\u8bfe\u65f6\u5185\u5bb9",
                "\u8bfe\u7a0b\u4e3b\u9898",
                "\u8bfe\u7a0b",
                "\u8bfe\u65f6",
            },
            "knowledge_points": {
                "\u77e5\u8bc6\u70b9",
                "\u6838\u5fc3\u77e5\u8bc6\u70b9",
                "\u91cd\u70b9",
                "\u91cd\u70b9\u96be\u70b9",
            },
        }
        header_map: dict[str, int] = {}
        for index, value in enumerate(normalized):
            if not value:
                continue
            for field, names in aliases.items():
                if field in header_map:
                    continue
                if value in names:
                    header_map[field] = index
                    break

        required_fields = {"week", "module", "lesson", "knowledge_points"}
        if required_fields.issubset(header_map):
            return header_map
        return None

    def _extract_titled_value(self, line: str, prefixes: tuple[str, ...]) -> str:
        label, value = _split_label_value(line)
        if not label or not value:
            return ""
        normalized_label = _normalize_label(label)
        for prefix in prefixes:
            if normalized_label.startswith(prefix):
                # Require digit or end-of-label after prefix to avoid false matches
                # e.g. "模块1" matches "模块" but "模块类别" does not
                after = normalized_label[len(prefix) :]
                if not after or after[0].isdigit():
                    return value
        return ""

    def _cell_value(self, row: list[str], index: int | None) -> str:
        if index is None or index < 0 or index >= len(row):
            return ""
        return row[index].strip()

    def _read_docx_paragraphs(self, binary: bytes) -> list[str]:
        with zipfile.ZipFile(io.BytesIO(binary)) as archive:
            document_xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(document_xml)
        paragraphs = []
        for paragraph in root.findall(".//w:p", WORD_NS):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", WORD_NS)]
            line = "".join(texts).strip()
            if line:
                paragraphs.append(line)
        return paragraphs

    def _read_xlsx_rows(self, binary: bytes) -> list[list[str]]:
        with zipfile.ZipFile(io.BytesIO(binary)) as archive:
            shared_strings = self._read_shared_strings(archive)
            sheet_xml = archive.read("xl/worksheets/sheet1.xml")
        root = ElementTree.fromstring(sheet_xml)
        rows: list[list[str]] = []
        for row in root.findall(".//s:sheetData/s:row", SHEET_NS):
            values: list[str] = []
            for cell in row.findall("s:c", SHEET_NS):
                column_index = self._cell_column_index(cell)
                while len(values) < column_index:
                    values.append("")
                values.append(self._read_cell_text(cell, shared_strings))
            rows.append(values)
        return rows

    def _cell_column_index(self, cell: ElementTree.Element) -> int:
        reference = (cell.get("r") or "").strip()
        letters = "".join(char for char in reference if char.isalpha()).upper()
        if not letters:
            return 0
        index = 0
        for letter in letters:
            index = index * 26 + (ord(letter) - 64)
        return max(0, index - 1)

    def _read_shared_strings(self, archive: zipfile.ZipFile) -> list[str]:
        try:
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        except KeyError:
            return []
        values = []
        for item in root.findall("s:si", SHEET_NS):
            parts = [node.text or "" for node in item.findall(".//s:t", SHEET_NS)]
            values.append("".join(parts))
        return values

    def _read_cell_text(self, cell: ElementTree.Element, shared_strings: list[str]) -> str:
        value_node = cell.find("s:v", SHEET_NS)
        if value_node is None or value_node.text is None:
            return ""
        text = value_node.text
        if cell.get("t") == "s":
            try:
                return shared_strings[int(text)]
            except (ValueError, IndexError):
                return ""
        return text

    def _rebuild_course_indexes(self, user_id: str, course_id: str) -> dict[str, Any]:
        documents = self.storage.list_documents(user_id)
        course_documents = []
        modules_map: OrderedDict[str, dict[str, Any]] = OrderedDict()
        lessons_map: OrderedDict[str, dict[str, Any]] = OrderedDict()
        knowledge_points: list[str] = []
        summary = ""
        course_name = ""

        for row in documents:
            document = row.get("document") or {}
            parsed = row.get("parsed") or {}
            if document.get("course_id") != course_id:
                continue

            course_documents.append(
                {
                    "document_id": document.get("document_id", ""),
                    "title": document.get("title", ""),
                    "doc_kind": document.get("doc_kind", ""),
                    "original_filename": document.get("original_filename", ""),
                    "updated_at": document.get("updated_at", ""),
                }
            )
            if not course_name:
                course_name = parsed.get("course_name", "")
            if not summary:
                summary = parsed.get("summary", "")
            for module in parsed.get("modules", []) or []:
                title = str(module.get("title", "")).strip()
                if title and title not in modules_map:
                    modules_map[title] = {
                        "module_id": module.get("module_id") or f"mod_{_course_hash(title)}",
                        "title": title,
                    }
            for lesson in parsed.get("lessons", []) or []:
                title = str(lesson.get("title", "")).strip()
                lesson_key = f"{document.get('document_id', '')}:{title}"
                if title and lesson_key not in lessons_map:
                    lessons_map[lesson_key] = {
                        "lesson_id": lesson.get("lesson_id") or f"lesson_{_course_hash(title)}",
                        "title": title,
                    }
            for point in parsed.get("knowledge_points", []) or []:
                label = str(point).strip()
                if label and label not in knowledge_points:
                    knowledge_points.append(label)

        course_map = self.storage.load_course_map(user_id)
        courses = [
            row
            for row in course_map.get("courses", [])
            if row.get("course_id") != course_id
        ]

        # If no documents remain for this course, remove it entirely
        if not course_documents:
            self.storage.save_course_catalog(user_id, course_id, {})
            self.storage.save_chunk_index(user_id, course_id, [])
            self.storage.save_course_map(user_id, {"courses": courses})
            self._sync_vector_index(user_id, course_id, [])
            return {
                "catalog": {},
                "chunks": [],
                "course_map": {},
            }

        catalog = CourseCatalog(
            course_id=course_id,
            course_name=course_name,
            user_id=user_id,
            summary=summary,
            module_ids=[item["module_id"] for item in modules_map.values()],
            knowledge_point_ids=[f"kp_{_course_hash(label)}" for label in knowledge_points],
        ).to_dict()
        chunks = self._build_chunks(course_id, course_documents, documents)
        self.storage.save_course_catalog(user_id, course_id, catalog)
        self.storage.save_chunk_index(user_id, course_id, chunks)
        self._sync_vector_index(user_id, course_id, chunks)

        current_course = {
            "course_id": course_id,
            "course_name": course_name,
            "summary": summary,
            "documents": course_documents,
            "modules": list(modules_map.values()),
            "lessons": list(lessons_map.values()),
            "knowledge_points": [
                {
                    "knowledge_point_id": f"kp_{_course_hash(label)}",
                    "label": label,
                }
                for label in knowledge_points
            ],
            "counts": {
                "documents": len(course_documents),
                "modules": len(modules_map),
                "lessons": len(lessons_map),
                "knowledge_points": len(knowledge_points),
            },
            "updated_at": self.now_provider(),
        }
        courses.append(current_course)
        courses.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        self.storage.save_course_map(user_id, {"courses": courses})
        return {
            "catalog": catalog,
            "chunks": chunks,
            "course_map": current_course,
        }

    def _build_chunks(
        self,
        course_id: str,
        course_documents: list[dict[str, Any]],
        documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        document_lookup = {row.get("document", {}).get("document_id"): row for row in documents}
        chunks: list[dict[str, Any]] = []
        for document in course_documents:
            parsed = (document_lookup.get(document["document_id"]) or {}).get("parsed", {})
            for module in parsed.get("modules", []) or []:
                title = str(module.get("title", "")).strip()
                if not title:
                    continue
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"chunk_{_course_hash(course_id, document['document_id'], title)}",
                        course_id=course_id,
                        document_id=document["document_id"],
                        doc_kind=document["doc_kind"],
                        section=title,
                        chunk_type="module_outline",
                        text=title,
                        keywords=_tokenize_points(title),
                        evidence_label=document["title"],
                    ).to_dict()
                )
            for lesson in parsed.get("lessons", []) or []:
                title = str(lesson.get("title", "")).strip()
                if not title:
                    continue
                points = [str(item) for item in lesson.get("knowledge_points", []) or []]
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=f"chunk_{_course_hash(course_id, document['document_id'], title)}",
                        course_id=course_id,
                        document_id=document["document_id"],
                        doc_kind=document["doc_kind"],
                        section=title,
                        chunk_type="lesson_outline",
                        text=title,
                        keywords=points,
                        knowledge_point_ids=[f"kp_{_course_hash(point)}" for point in points],
                        evidence_label=document["title"],
                    ).to_dict()
                )
        return chunks
