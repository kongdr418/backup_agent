from __future__ import annotations

import os


EMBEDDING_MODEL_NAME = os.environ.get(
    "COURSE_KNOWLEDGE_EMBEDDING_MODEL",
    "BAAI/bge-small-zh-v1.5",
).strip()

# 国内镜像站，本地无缓存时优先从这里下载
# 可通过环境变量 HF_ENDPOINT 自定义，默认使用 hf-mirror.com
HF_MIRROR_ENDPOINT = os.environ.get(
    "HF_ENDPOINT",
    "https://hf-mirror.com",
).strip().rstrip("/")

VECTOR_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30
MIN_VECTOR_SCORE = 0.45
MIN_HYBRID_SCORE = 0.38
STRONG_KEYWORD_SCORE = 0.60
MAX_EVIDENCE_RESULTS = 6
MAX_KNOWLEDGE_POINTS = 6
MAX_LESSONS = 4
MIN_COURSE_MATCH_SCORE = 0.45

