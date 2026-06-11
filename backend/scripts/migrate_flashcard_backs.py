# -*- coding: utf-8 -*-
"""一次性迁移脚本:把历史 flashcard 里 back 字段还是字母的旧卡,重算成选项文本。

触发原因:
  旧版 study_tools_mistake_to_flashcard 写 back = correct_answer (字母 'B' / 'A / C'),
  修复后写 back = 字母映射回 options 后的文本 ('2' / '2 / 4')。
  本脚本把所有 source='mistake' 且 back 是纯字母模式的老卡升级到新格式。

数据源优先级:
  1) mistake.options (在 _sync_classroom_mistakes 改造后写入的,首选)
  2) classroom 题里的 options (旧错题没存 options 时的兜底)

用法:
  PYTHONIOENCODING=utf-8 python backend/scripts/migrate_flashcard_backs.py [--dry-run]
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from interactive_classroom.storage import ClassroomStorage  # noqa: E402
from study_tools.storage import StudyToolsStorage, _clean_text  # noqa: E402

BACKEND_DIR = str(ROOT)
CLASSROOM_STORAGE = ClassroomStorage(BACKEND_DIR)
STUDY_TOOLS_STORAGE = StudyToolsStorage(BACKEND_DIR)

USERS_DIR = Path(BACKEND_DIR) / "study_tools" / "users"

_LETTER_BACK = re.compile(r"^[A-H](\s*/\s*[A-H])*$")
_LETTER_PREFIX = re.compile(r"^\(?([A-H])[\.、\s)]")


def _strip_option_prefix(label: str) -> str:
    return _LETTER_PREFIX.sub("", str(label or "")).strip()


def _parse_correct_letters(correct: str) -> list[str]:
    text = str(correct or "").strip()
    if not text:
        return []
    parts = re.split(r"[\s/,,，、|]+", text)
    out: list[str] = []
    for p in parts:
        p = p.strip().upper()
        if p and len(p) == 1 and p.isalpha() and p not in out:
            out.append(p)
    return out


def _letter_to_text(correct_answer: str, options: list[str]) -> str | None:
    """双路匹配:label 带 'A. ' 前缀按字母查;无前缀时按 A/B/C 索引 fallback。"""
    if not options:
        return None
    options = [str(o or "").strip() for o in options if str(o or "").strip()]
    by_letter: dict[str, str] = {}
    for opt in options:
        m = _LETTER_PREFIX.match(opt)
        if m:
            by_letter[m.group(1).upper()] = _strip_option_prefix(opt)
    letters = _parse_correct_letters(correct_answer)
    if not letters:
        return None
    parts: list[str] = []
    for letter in letters:
        if letter in by_letter:
            parts.append(by_letter[letter])
        else:
            idx = ord(letter) - ord("A")
            if 0 <= idx < len(options):
                parts.append(_strip_option_prefix(options[idx]))
    if not parts:
        return None
    return " / ".join(parts)


def _load_mistake_options_from_classroom(user_id: str, source_ref: dict, storage: StudyToolsStorage) -> list[str] | None:
    """旧错题未存 options 时,fallback 到原课堂的题里取 options。"""
    if not storage:
        return None
    cid = (source_ref or {}).get("classroom_id", "")
    qid = (source_ref or {}).get("question_id", "")
    if not cid or not qid:
        return None
    classroom = CLASSROOM_STORAGE.load_classroom(user_id, cid)
    if not classroom:
        return None
    for scene in classroom.get("scenes") or []:
        for q in (scene.get("content") or {}).get("questions") or []:
            if str(q.get("id") or "") == qid:
                raw = q.get("options") or []
                out: list[str] = []
                for opt in raw:
                    if isinstance(opt, dict):
                        label = str(opt.get("label") or opt.get("value") or "").strip()
                        if label:
                            out.append(label)
                    else:
                        text = str(opt or "").strip()
                        if text:
                            out.append(text)
                return out or None
    return None


def migrate_user(user_id: str, dry_run: bool) -> tuple[int, int, int]:
    """返回 (扫描张数, 已升级张数, 跳过/失败张数)。"""
    fp = USERS_DIR / user_id / "flashcards.json"
    if not fp.exists():
        return (0, 0, 0)
    try:
        d = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ! {user_id}: 读文件失败 {e}")
        return (0, 0, 0)
    items = d.get("items") or []
    scanned = 0
    upgraded = 0
    skipped = 0

    mp_path = USERS_DIR / user_id / "mistakes.json"
    mistakes_by_id: dict[str, dict] = {}
    if mp_path.exists():
        try:
            md = json.loads(mp_path.read_text(encoding="utf-8"))
            for m in md.get("items") or []:
                if isinstance(m, dict) and m.get("id"):
                    mistakes_by_id[m["id"]] = m
        except Exception:
            pass

    for c in items:
        scanned += 1
        if c.get("source") != "mistake":
            skipped += 1
            continue
        back = _clean_text(c.get("back") or "", 4000)
        if not _LETTER_BACK.match(back):
            skipped += 1
            continue

        source_id = (c.get("source_id") or "").strip()
        mistake = mistakes_by_id.get(source_id) or {}
        correct = mistake.get("correct_answer") or ""
        options = mistake.get("options") or []
        if not options:
            options = _load_mistake_options_from_classroom(user_id, c.get("source_ref") or {}, STUDY_TOOLS_STORAGE) or []
        new_back = _letter_to_text(correct, options) if options else None
        if not new_back or new_back == back:
            skipped += 1
            print(f"  - card={c.get('id')} back={back!r} 无法映射(source_id={source_id})")
            continue

        print(f"  ✓ card={c.get('id')}  {back!r} → {new_back!r}")
        c["back"] = new_back
        c["updated_at"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
        upgraded += 1

    if upgraded and not dry_run:
        # 原子写盘:写 tmp 再 os.replace
        tmp = fp.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, fp)
    return (scanned, upgraded, skipped)


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN (不写盘) ===")
    print(f"扫描目录: {USERS_DIR}")

    total_scanned = total_upgraded = total_skipped = 0
    for user_dir in sorted(USERS_DIR.iterdir()):
        if not user_dir.is_dir():
            continue
        user_id = user_dir.name
        s, u, k = migrate_user(user_id, dry_run)
        if s:
            print(f"\n[{user_id}] scanned={s} upgraded={u} skipped={k}")
        total_scanned += s
        total_upgraded += u
        total_skipped += k

    print("\n" + "=" * 50)
    print(f"总扫描: {total_scanned}  升级: {total_upgraded}  跳过: {total_skipped}")
    if dry_run:
        print("(dry-run 模式,未写盘 — 去掉 --dry-run 真正执行)")


if __name__ == "__main__":
    main()
