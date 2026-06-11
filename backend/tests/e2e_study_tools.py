# -*- coding: utf-8 -*-
"""M1 端到端测试 - 学习工具 API。"""
import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import date, timedelta


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9_一-龥-]+", "-", s.lower()).strip("-")[:64] or f"x{time.time_ns()}"

BASE = "http://127.0.0.1:5000/api/study-tools"
USER = f"e2e-{int(time.time())}"


def call(method, path, body=None, expect=200):
    url = BASE + path
    # 跟前端 api/client.ts 一致：POST/PATCH 把 user_id 塞 body, GET/DELETE 走 query
    if body is None:
        body = {}
    if method.upper() in ("POST", "PATCH", "PUT"):
        if "user_id" not in body:
            body = {**body, "user_id": USER}
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    else:
        # GET / DELETE — 走 query string
        sep = "&" if "?" in path else "?"
        url = f"{url}{sep}user_id={USER}"
        data = None
    headers = {} if data is None else {"Content-Type": "application/json"}
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers=headers,
    )
    try:
        resp = urllib.request.urlopen(req)
        status = resp.status
        payload = json.loads(resp.read().decode("utf-8"))
        resp.close()
    except urllib.error.HTTPError as e:
        status = e.code
        raw_body = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw_body)
        except Exception:
            payload = {"raw": raw_body[:300]}
    if expect is not None and status != expect:
        print(f"  ✗ {method} {path} → {status} (expected {expect})")
        print(f"    body = {json.dumps(payload, ensure_ascii=False)[:300]}")
        return None
    print(f"  ✓ {method} {path} → {status}")
    return payload


print(f"=== user: {USER} ===")

print("\n--- 1. POST /mistakes (manual) ---")
KP1 = "函数代入"
COURSE1 = "高三数学"
r = call("POST", "/mistakes", {
    "stem": "已知函数 f(x)=x^2,求 f(3) 的值",
    "correct_answer": "9",
    "user_answer": "6",
    "analysis": "代入 x=3",
    "course_name": COURSE1,
    "course_id": f"c_{slugify(COURSE1)}",
    "knowledge_point_name": KP1,
    "knowledge_point_id": f"kp_{slugify(KP1)}",
    "tags": ["基础"],
}, expect=201)
assert r and r["success"], "POST /mistakes failed"
M1_ID = r["item"]["id"]
print(f"    id = {M1_ID}")

print("\n--- 2. POST /mistakes/bulk (classroom) ---")
r = call("POST", "/mistakes/bulk", {
    "items": [
        {"stem": "集合 A={1,2},B={2,3},A∩B=?",
         "correct_answer": "{2}", "source": "classroom",
         "source_evidence_id": "ev_classroom_q1",
         "course_name": "高三数学",
         "course_id": f"c_{slugify('高三数学')}",
         "knowledge_point_name": "集合运算",
         "knowledge_point_id": f"kp_{slugify('集合运算')}"},
        {"stem": "求极限 lim x→0 sin(x)/x",
         "correct_answer": "1", "source": "classroom",
         "source_evidence_id": "ev_classroom_q2",
         "course_name": "高三数学",
         "course_id": f"c_{slugify('高三数学')}",
         "knowledge_point_name": "极限",
         "knowledge_point_id": f"kp_{slugify('极限')}"},
    ]
}, expect=200)
assert r and r["added_count"] == 2, f"bulk first call should add 2, got {r}"
print(f"    added={r['added_count']} deduped={r['deduped_count']}")

print("\n--- 3. POST /mistakes/bulk again (same ev ids → dedup) ---")
r = call("POST", "/mistakes/bulk", {
    "items": [
        {"stem": "重复项", "correct_answer": "x",
         "source": "classroom", "source_evidence_id": "ev_classroom_q1",
         "course_name": "高三数学"},
    ]
}, expect=200)
assert r and r["added_count"] == 0 and r["deduped_count"] == 1, \
    f"dedup test failed: added={r['added_count']} deduped={r['deduped_count']}"
print(f"    added={r['added_count']} deduped={r['deduped_count']} ✓ 幂等正确")

print("\n--- 4. GET /mistakes ---")
r = call("GET", "/mistakes?page_size=10", expect=200)
print(f"    total = {r['total']}")
for x in r["items"]:
    print(f"    - {x['id'][:22]} | {x['source']:8s} | {x.get('knowledge_point_name','')}")
assert r["total"] == 3, f"expected 3 mistakes, got {r['total']}"

print("\n--- 5. GET /stats (before mastery) ---")
r = call("GET", "/stats", expect=200)
print(f"    mistakes: total={r['mistakes']['total']} mastered={r['mistakes']['mastered']} unmastered={r['mistakes']['unmastered']}")
print(f"    top_kp: {r['mistakes']['top_knowledge_points']}")
assert r["mistakes"]["total"] == 3
assert r["mistakes"]["unmastered"] == 3

print("\n--- 6. PATCH /mistakes/<id> mastered=true ---")
r = call("PATCH", f"/mistakes/{M1_ID}", {"mastered": True}, expect=200)
print(f"    mastered={r['item']['mastered']} mastered_at={r['item']['mastered_at']}")
assert r["item"]["mastered"] is True
assert r["item"]["mastered_at"] is not None

print("\n--- 7. GET /stats (after mastery) ---")
r = call("GET", "/stats", expect=200)
assert r["mistakes"]["mastered"] == 1
assert r["mistakes"]["unmastered"] == 2
print(f"    mastered={r['mistakes']['mastered']} unmastered={r['mistakes']['unmastered']} ✓")

print("\n--- 8. POST /mistakes/<id>/to-flashcard ---")
r = call("POST", f"/mistakes/{M1_ID}/to-flashcard", {}, expect=201)
C1_ID = r["item"]["id"]
print(f"    card_id = {C1_ID}")
print(f"    source  = {r['item']['source']}")
print(f"    sm2     = {r['item']['sm2']}")
print(f"    front   = {r['item']['front'][:50]}")
assert r["item"]["source"] == "mistake"

print("\n--- 9. POST /flashcards/<id>/review grade=5 (1st) ---")
r = call("POST", f"/flashcards/{C1_ID}/review", {"grade": 5}, expect=200)
sm2 = r["item"]["sm2"]
print(f"    reps={sm2['repetitions']}  EF={sm2['ease_factor']}  interval={sm2['interval_days']}  due={sm2['due_date']}")
assert sm2["repetitions"] == 1
assert sm2["ease_factor"] == 2.6
assert sm2["interval_days"] == 1

print("\n--- 10. POST /flashcards/<id>/review grade=5 (2nd) ---")
r = call("POST", f"/flashcards/{C1_ID}/review", {"grade": 5}, expect=200)
sm2 = r["item"]["sm2"]
print(f"    reps={sm2['repetitions']}  EF={sm2['ease_factor']}  interval={sm2['interval_days']}  due={sm2['due_date']}")
assert sm2["repetitions"] == 2
assert sm2["interval_days"] == 6

print("\n--- 11. POST /flashcards/<id>/review grade=4 (3rd, harder) ---")
r = call("POST", f"/flashcards/{C1_ID}/review", {"grade": 4}, expect=200)
sm2 = r["item"]["sm2"]
print(f"    reps={sm2['repetitions']}  EF={sm2['ease_factor']}  interval={sm2['interval_days']}  due={sm2['due_date']}")
assert sm2["repetitions"] == 3
# EF was 2.7, + (0.1 - (5-4)*(0.08+0.02)) = 2.7 + 0 = 2.7
# interval = round(6 * 2.7) = 16
assert sm2["interval_days"] == 16

print("\n--- 12. POST /flashcards/<id>/review grade=0 (fail) ---")
r = call("POST", f"/flashcards/{C1_ID}/review", {"grade": 0}, expect=200)
sm2 = r["item"]["sm2"]
print(f"    reps={sm2['repetitions']}  EF={sm2['ease_factor']}  interval={sm2['interval_days']}  due={sm2['due_date']}")
# EF: 2.7 + (0.1 - 5*(0.08+5*0.02)) = 2.7 + (0.1 - 0.9) = 1.9
# grade<3 → reps=0, interval=1
assert sm2["repetitions"] == 0
assert sm2["interval_days"] == 1
print(f"    ✓ 重置为 reps=0, interval=1, EF 下降")

print("\n--- 13. GET /flashcards/due (after failure → card is due TOMORROW, not today) ---")
r = call("GET", "/flashcards/due?limit=10", expect=200)
print(f"    total = {r['total']} (grade=0 后 due_date=today+1,所以今日待复习为 0)")
for x in r["items"]:
    print(f"    - {x['id'][:22]} | due: {x['sm2']['due_date']}")
# After grade=0, due_date = today+1, so it's NOT in today's due list
assert r["total"] == 0, f"expected 0 due cards, got {r['total']}"

print("\n--- 14. GET /flashcard by id + verify due_date shifted to tomorrow ---")
r = call("GET", f"/flashcards/{C1_ID}", expect=200)
print(f"    due_date = {r['item']['sm2']['due_date']} (expected: tomorrow)")
expected_due = (date.today() + timedelta(days=1)).isoformat()
assert r["item"]["sm2"]["due_date"] == expected_due, \
    f"expected {expected_due}, got {r['item']['sm2']['due_date']}"
print(f"    ✓ 失败重置为明天复习")

print("\n--- 14b. Add new card, manually set due_date=today, verify in /due list ---")
r = call("POST", "/flashcards", {
    "front": "测试卡 1",
    "back": "答案 1",
    "course_name": "测试",
    "source": "manual",
}, expect=201)
DUE_CARD_ID = r["item"]["id"]
today = date.today().isoformat()
r = call("PATCH", f"/flashcards/{DUE_CARD_ID}", {"sm2": {"due_date": today}}, expect=200)
assert r["item"]["sm2"]["due_date"] == today
r = call("GET", "/flashcards/due?limit=10", expect=200)
print(f"    total = {r['total']}")
ids = [x["id"] for x in r["items"]]
assert DUE_CARD_ID in ids, f"expected {DUE_CARD_ID} in due list, got {ids}"
print(f"    ✓ 今日待复习列表正确返回该卡")

print("\n--- 15. GET /stats final ---")
r = call("GET", "/stats", expect=200)
print(f"    mistakes: total={r['mistakes']['total']} mastered={r['mistakes']['mastered']}")
print(f"    flashcards: total={r['flashcards']['total']} due_today={r['flashcards']['due_today']}")
print(f"    streak_days={r['flashcards']['streak_days']}")

print("\n--- 16. DELETE /flashcards/<id> (C1) ---")
r = call("DELETE", f"/flashcards/{C1_ID}", expect=200)
print(f"    body = {r}")

print("\n--- 17. DELETE /flashcards/<id> (DUE_CARD) ---")
r = call("DELETE", f"/flashcards/{DUE_CARD_ID}", expect=200)
print(f"    body = {r}")

print("\n--- 18. DELETE /mistakes/<id> ---")
r = call("DELETE", f"/mistakes/{M1_ID}", expect=200)
print(f"    body = {r}")

print("\n--- 19. VERIFY learner_profile evidence (学情联动) ---")
# 错题入库 / 标记掌握 / 闪卡复习 三个动作都应该向 learner_profile 推 evidence
profile_url = f"http://127.0.0.1:5000/api/learner-profile?user_id={USER}"
import urllib.request as _ur
with _ur.urlopen(_ur.Request(profile_url, method="GET")) as resp:
    profile_resp = json.loads(resp.read().decode("utf-8"))
profile = profile_resp.get("profile", {})
# evidence_buffer 是 dict[course_id][kp_id] → {observations: [evidence, ...]}
buf = profile.get("evidence_buffer", {})
all_evs = []
for course_id, course_buf in buf.items():
    if not isinstance(course_buf, dict):
        continue
    for kp_id, kp_buf in course_buf.items():
        if not isinstance(kp_buf, dict):
            continue
        for ev in kp_buf.get("observations", []):
            if isinstance(ev, dict):
                all_evs.append(ev)
print(f"    evidence_buffer 总数 = {len(all_evs)}")
ev_ids = [e.get("source_id", "") for e in all_evs]
print(f"    所有 source_id:")
for s in ev_ids:
    print(f"      - {s}")
# 关键检查:错题入库 + 标记掌握 + 闪卡复习 三类 source_id 都应存在
# M1_ID 已是 'mk_xxx' 形式,而 source_id 是 'mk_<mk_id>_<reason>',所以匹配 'mk_<M1_ID>_<reason>' 即 'mk_mk_xxx_<reason>'
has_mistake_added = any(f"mk_{M1_ID}_wrong_answer" in s for s in ev_ids)
has_mistake_mastered = any(f"mk_{M1_ID}_mistake_mastered" in s for s in ev_ids)
has_card_reviewed = any(f"fc_{C1_ID}_" in s for s in ev_ids)
print(f"\n    错题入库 evidence     : {'✓' if has_mistake_added else '✗'}")
print(f"    错题标记掌握 evidence : {'✓' if has_mistake_mastered else '✗'}")
print(f"    闪卡复习 evidence     : {'✓' if has_card_reviewed else '✗'}")
assert has_mistake_added, f"expected mistake-added evidence, ev_ids={ev_ids}"
assert has_mistake_mastered, f"expected mistake-mastered evidence, ev_ids={ev_ids}"
assert has_card_reviewed, f"expected flashcard review evidence, ev_ids={ev_ids}"
print(f"\n    ✓ 学情联动已打通:错题/掌握/复习三类操作都写入 evidence_buffer")

# ─────────────────────────────────────────────────
# 错题集 (mistake-collections) 端到端
# ─────────────────────────────────────────────────
print("\n--- 20. POST /mistake-collections 创建「Python错题集」 ---")
r = call("POST", "/mistake-collections", {"name": "Python错题集"}, expect=201)
assert r and r["success"], "POST /mistake-collections failed"
COLL_ID = r["item"]["id"]
assert r["item"]["name"] == "Python错题集"
print(f"    id={COLL_ID} ✓")

print("\n--- 20b. GET 确认初始 count=0 ---")
r = call("GET", "/mistake-collections", expect=200)
assert r["total"] == 1
assert r["items"][0]["id"] == COLL_ID
assert r["items"][0]["count"] == 0
print(f"    count=0 ✓")

print("\n--- 21. POST 同名集合 → 400 重名 ---")
r = call("POST", "/mistake-collections", {"name": "Python错题集"}, expect=400)
assert r and not r.get("success"), f"expected duplicate rejection, got {r}"
print(f"    ✓ 重名被拒: {r.get('error', '')}")

print("\n--- 22. POST /mistake-collections 创建第二个「考前复习」 ---")
r = call("POST", "/mistake-collections", {"name": "考前复习"}, expect=201)
COLL2_ID = r["item"]["id"]
print(f"    id={COLL2_ID}")

print("\n--- 23. GET /mistake-collections 应包含 2 个集合,count=0 ---")
r = call("GET", "/mistake-collections", expect=200)
assert r["total"] == 2
counts = {it["name"]: it["count"] for it in r["items"]}
assert counts["Python错题集"] == 0
assert counts["考前复习"] == 0
print(f"    total=2  counts={counts} ✓")

print("\n--- 24. 额外添加 2 道错题用于关联测试 ---")
M_PY1 = call("POST", "/mistakes", {
    "stem": "Python 列表推导式 [x*2 for x in range(5)] 的输出?",
    "correct_answer": "[0, 2, 4, 6, 8]",
    "user_answer": "[0, 2, 4, 6]",
    "course_name": "Python 基础",
    "knowledge_point_name": "列表推导式",
    "source": "manual",
}, expect=201)["item"]["id"]
M_PY2 = call("POST", "/mistakes", {
    "stem": "Python 中 dict.get('k', default) 的语义?",
    "correct_answer": "key 不存在时返回 default",
    "user_answer": "返回 None",
    "course_name": "Python 基础",
    "knowledge_point_name": "dict.get",
    "source": "manual",
}, expect=201)["item"]["id"]
M_REVIEW = call("POST", "/mistakes", {
    "stem": "二次函数顶点公式?",
    "correct_answer": "x = -b/(2a)",
    "user_answer": "x = b/(2a)",
    "course_name": "高三数学",
    "knowledge_point_name": "二次函数",
    "source": "manual",
}, expect=201)["item"]["id"]
print(f"    M_PY1={M_PY1[:18]}  M_PY2={M_PY2[:18]}  M_REVIEW={M_REVIEW[:18]}")

print("\n--- 25. POST .../<COLL>/mistakes 把 M_PY1 + M_PY2 加入「Python错题集」 ---")
r = call("POST", f"/mistake-collections/{COLL_ID}/mistakes",
         {"mistake_ids": [M_PY1, M_PY2]}, expect=200)
assert r["added"] == 2
assert r["not_found"] == []
print(f"    added={r['added']} not_found={r['not_found']} ✓")

print("\n--- 26. 同一道题再次加入同一集合 → 幂等(added=0) ---")
r = call("POST", f"/mistake-collections/{COLL_ID}/mistakes",
         {"mistake_ids": [M_PY1]}, expect=200)
assert r["added"] == 0, f"expected 0 added, got {r['added']}"
print(f"    added={r['added']} ✓ 幂等")

print("\n--- 27. GET /mistakes?collection_id=<COLL> 只返回 2 道 ---")
r = call("GET", f"/mistakes?collection_id={COLL_ID}", expect=200)
assert r["total"] == 2
ids = {it["id"] for it in r["items"]}
assert M_PY1 in ids and M_PY2 in ids
assert M_REVIEW not in ids
print(f"    total=2  ids match ✓")

print("\n--- 28. 同一道错题可以归入多个集合(M_PY1 也加入「考前复习」)---")
r = call("POST", f"/mistake-collections/{COLL2_ID}/mistakes",
         {"mistake_ids": [M_PY1, M_REVIEW]}, expect=200)
assert r["added"] == 2
print(f"    M_PY1 同时属于两个集合 ✓")

print("\n--- 29. GET /mistakes 列表中 M_PY1.collection_ids 应含 2 个 ---")
r = call("GET", "/mistakes?page_size=200", expect=200)
py1 = next(it for it in r["items"] if it["id"] == M_PY1)
assert len(py1["collection_ids"]) == 2
assert COLL_ID in py1["collection_ids"]
assert COLL2_ID in py1["collection_ids"]
print(f"    M_PY1.collection_ids 长度={len(py1['collection_ids'])} ✓ 多对多生效")

print("\n--- 30. GET /mistake-collections 计数应反映关联 ---")
r = call("GET", "/mistake-collections", expect=200)
counts = {it["name"]: (it["count"], it["unmastered_count"]) for it in r["items"]}
assert counts["Python错题集"] == (2, 2)
assert counts["考前复习"] == (2, 2)
print(f"    counts={counts} ✓")

print("\n--- 31. PATCH 重命名「Python错题集」→「Python基础错题」 ---")
r = call("PATCH", f"/mistake-collections/{COLL_ID}",
         {"name": "Python基础错题"}, expect=200)
assert r["item"]["name"] == "Python基础错题"
print(f"    新名称: {r['item']['name']} ✓")

print("\n--- 32. 重命名为已存在的「考前复习」→ 400 ---")
r = call("PATCH", f"/mistake-collections/{COLL_ID}",
         {"name": "考前复习"}, expect=400)
print(f"    ✓ 重名被拒: {r.get('error', '')}")

print("\n--- 33. DELETE .../mistakes/<id> 把 M_PY1 从「Python基础错题」移除 ---")
r = call("DELETE", f"/mistake-collections/{COLL_ID}/mistakes/{M_PY1}", expect=200)
print(f"    ✓ 移除成功")

print("\n--- 34. 重新查询 M_PY1,collection_ids 应仅剩 1 个 ---")
r = call("GET", f"/mistakes/{M_PY1}", expect=200)
assert len(r["item"]["collection_ids"]) == 1
assert r["item"]["collection_ids"][0] == COLL2_ID
print(f"    collection_ids={r['item']['collection_ids']} ✓")

print("\n--- 35. DELETE /mistake-collections/<COLL2> 集合 ---")
r = call("DELETE", f"/mistake-collections/{COLL2_ID}", expect=200)
print(f"    ✓ 已删除「考前复习」")

print("\n--- 36. 集合删除后,内部错题仍存在但 collection_ids 已清空 ---")
r = call("GET", f"/mistakes/{M_PY1}", expect=200)
assert r["item"]["collection_ids"] == []
r = call("GET", f"/mistakes/{M_REVIEW}", expect=200)
assert r["item"]["collection_ids"] == []
print(f"    M_PY1.collection_ids={r['item']['collection_ids']} ✓ 错题未被删除")

print("\n--- 37. 删除不存在的集合 → 404 ---")
r = call("DELETE", "/mistake-collections/mc_does_not_exist", expect=404)
print(f"    ✓ 404")

print("\n--- 38. PATCH 不存在的集合 → 404 ---")
r = call("PATCH", "/mistake-collections/mc_does_not_exist",
         {"name": "x"}, expect=404)
print(f"    ✓ 404")

print("\n--- 39. 清理:删除剩余的「Python基础错题」 ---")
r = call("DELETE", f"/mistake-collections/{COLL_ID}", expect=200)
print(f"    ✓")


# ==================== 错题图片附件 e2e ====================

import io
import uuid as _uuid

# 1×1 透明 PNG(67 字节,合法魔数)
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\x00"
    b"\x00\x00\x03\x00\x01\x95\xb1\x88\x80"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
TINY_JPG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01"
    b"\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07"
    b"\x07\x09\x09\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f"
    b"\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
    b"\xff\xd9"
)


def call_multipart(path, files, fields=None, expect=201):
    """最小 multipart 上传工具:files=[(filename, content_bytes, mime), ...]"""
    boundary = "----e2e" + _uuid.uuid4().hex
    body = io.BytesIO()
    for fname, content, mime in files:
        body.write(f"--{boundary}\r\n".encode())
        body.write(
            f'Content-Disposition: form-data; name="files"; filename="{fname}"\r\n'.encode()
        )
        body.write(f"Content-Type: {mime}\r\n\r\n".encode())
        body.write(content)
        body.write(b"\r\n")
    for k, v in (fields or {}).items():
        body.write(f"--{boundary}\r\n".encode())
        body.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        body.write(str(v).encode())
        body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())
    url = BASE + path + (f"&user_id={USER}" if "?" in path else f"?user_id={USER}")
    req = urllib.request.Request(
        url,
        data=body.getvalue(),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        resp = urllib.request.urlopen(req)
        status = resp.status
        payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"raw": raw[:300]}
    if expect is not None and status != expect:
        print(f"  ✗ multipart POST {path} → {status} (expected {expect})")
        print(f"    body = {json.dumps(payload, ensure_ascii=False)[:300]}")
        return None
    print(f"  ✓ multipart POST {path} → {status}")
    return payload


def fetch_bytes(path, expect=200):
    url = BASE + path + (f"&user_id={USER}" if "?" in path else f"?user_id={USER}")
    req = urllib.request.Request(url, method="GET")
    try:
        resp = urllib.request.urlopen(req)
        status = resp.status
        data = resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
        data = e.read()
    if expect is not None and status != expect:
        print(f"  ✗ GET {path} → {status} (expected {expect})")
        return None
    return status, data


print("\n--- 40. POST /mistakes (multipart 带 1 张 PNG) ---")
payload = json.dumps({
    "stem": "[图题] 求 f(2) 的值",
    "correct_answer": "4",
    "course_name": "高三数学",
    "course_id": f"c_{slugify('高三数学')}",
    "knowledge_point_name": "函数代入",
    "knowledge_point_id": f"kp_{slugify('函数代入')}",
    "tags": ["图题"],
}, ensure_ascii=False)
r = call_multipart(
    "/mistakes",
    files=[("sample.png", TINY_PNG, "image/png")],
    fields={"payload": payload, "user_id": USER},
    expect=201,
)
assert r and r["success"], "multipart create failed"
M_ATT_ID = r["item"]["id"]
att = r["item"]["attachments"]
assert len(att) == 1, f"attachments should be 1, got {len(att)}: {att}"
assert att[0]["id"].startswith("att_"), att[0]
assert att[0]["url"].startswith(f"/api/study-tools/mistakes/{M_ATT_ID}/attachments/{att[0]['id']}"), att[0]
assert f"user_id={USER}" in att[0]["url"], att[0]
assert att[0]["mime"] == "image/png", att[0]
assert att[0]["size"] == len(TINY_PNG)
print(f"    id={M_ATT_ID}  att_id={att[0]['id']}  size={att[0]['size']} ✓")

print("\n--- 41. GET 附件 → 200 + 字节与上传一致 ---")
status, data = fetch_bytes(f"/mistakes/{M_ATT_ID}/attachments/{att[0]['id']}", expect=200)
assert data == TINY_PNG, f"bytes mismatch: {len(data)} vs {len(TINY_PNG)}"
print(f"    bytes match ✓ ({len(data)})")

print("\n--- 42. GET 不存在的附件 → 404 ---")
r = call("GET", f"/mistakes/{M_ATT_ID}/attachments/att_xxxxxxxxxxxx", expect=404)
print(f"    ✓ 404")

print("\n--- 43. POST 追加 1 张 JPG ---")
r = call_multipart(
    f"/mistakes/{M_ATT_ID}/attachments",
    files=[("answer.jpg", TINY_JPG, "image/jpeg")],
    fields={"user_id": USER},
    expect=201,
)
assert r and r["success"]
att2 = r["item"]["attachments"]
assert len(att2) == 2, f"expected 2 attachments, got {len(att2)}"
print(f"    total attachments = {len(att2)} ✓")

print("\n--- 44. POST 追加 1 个 .txt 文件 → 400 拒绝 ---")
r = call_multipart(
    f"/mistakes/{M_ATT_ID}/attachments",
    files=[("notes.txt", b"hello world", "text/plain")],
    fields={"user_id": USER},
    expect=400,
)
print(f"    ✓ rejected: {r.get('error') if r else 'no body'}")

print("\n--- 45. POST 伪 PNG(扩展名是 png 但内容是文本) → 嗅探丢弃,saved 为空但仍 201 ---")
r = call_multipart(
    f"/mistakes/{M_ATT_ID}/attachments",
    files=[("fake.png", b"this is plain text", "image/png")],
    fields={"user_id": USER},
    expect=201,
)
assert r["saved"] == [], "嗅探失败的应被丢弃"
print(f"    ✓ 嗅探丢弃,saved={r['saved']}")

print("\n--- 46. POST 追加到不存在的错题 → 404 ---")
r = call_multipart(
    "/mistakes/mk_does_not_exist/attachments",
    files=[("x.png", TINY_PNG, "image/png")],
    fields={"user_id": USER},
    expect=404,
)
print(f"    ✓ 404")

print("\n--- 47. DELETE 第一个附件 → 200,列表剩 1 ---")
r = call("DELETE", f"/mistakes/{M_ATT_ID}/attachments/{att[0]['id']}", expect=200)
assert r and r["item"]["attachments"][0]["id"] == att2[1]["id"]
print(f"    ✓ 剩余 {len(r['item']['attachments'])} 张")

print("\n--- 48. 删除错题后,磁盘上的 attachments 目录也被清理 ---")
r = call("DELETE", f"/mistakes/{M_ATT_ID}", expect=200)
att_dir = f"backend/study_tools/users/{USER}/attachments/{M_ATT_ID}"
import os as _os
assert not _os.path.isdir(att_dir), f"目录应被删除,但仍存在: {att_dir}"
print(f"    ✓ {att_dir} 已清理")

print("\n" + "=" * 50)
print("✅ 附件流 9 项 e2e 检查通过")


print("\n" + "=" * 50)
print("✅ M1 全部 19 项 + 错题集 20 项 + 附件流 9 项 e2e 检查通过")
