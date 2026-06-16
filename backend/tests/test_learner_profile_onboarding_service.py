import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from learner_profile.onboarding_service import ProfileOnboardingService


def _profile():
    return {
        "basic": {
            "display_name": "",
            "learning_stage": "",
            "learning_basis": "",
            "background": "",
        },
        "preferences": {
            "goal": "",
            "content_style": [],
            "preferred_difficulty": "",
            "tutoring_style": "",
        },
        "global_traits": {
            "cognitive_preferences": {},
            "interest_directions": [],
        },
    }


def test_onboarding_uses_local_extraction_before_llm_for_guided_answers():
    calls = []

    def llm_call(**kwargs):
        calls.append(kwargs)
        return ""

    service = ProfileOnboardingService(llm_call=llm_call)

    result = service.advance(
        profile=_profile(),
        messages=[
            {"role": "assistant", "content": "先认识一下你：你目前处于什么学习阶段或年级？"},
            {"role": "user", "content": "大一"},
        ],
        llm_config={"model": "mimo-v2.5"},
    )

    assert calls == []
    assert result["draft"]["basic"]["learning_stage"] == "大一"
    assert result["current_field"] == "learning_basis"


def test_onboarding_still_falls_back_to_llm_when_local_extraction_cannot_advance():
    calls = []

    def llm_call(**kwargs):
        calls.append(kwargs)
        return '{"extracted":{"basic":{"learning_stage":"大二"}}}'

    service = ProfileOnboardingService(llm_call=llm_call)

    result = service.advance(
        profile=_profile(),
        messages=[
            {"role": "assistant", "content": "先认识一下你：你目前处于什么学习阶段或年级？"},
            {"role": "user", "content": "我是第二个学年"},
        ],
        llm_config={"model": "mimo-v2.5"},
    )

    assert len(calls) == 1
    assert result["draft"]["basic"]["learning_stage"] == "大二"


def test_onboarding_extracts_multiple_profile_fields_from_natural_answer():
    calls = []

    def llm_call(**kwargs):
        calls.append(kwargs)
        return ""

    service = ProfileOnboardingService(llm_call=llm_call)

    result = service.advance(
        profile=_profile(),
        messages=[
            {"role": "assistant", "content": "先认识一下你：你目前处于什么学习阶段或年级？"},
            {
                "role": "user",
                "content": "我是大一软件工程专业，学过 Python 爬虫，零基础，想做项目，喜欢案例和代码实操，对 AI 和软件开发感兴趣。",
            },
        ],
        llm_config={"model": "mimo-v2.5"},
    )

    draft = result["draft"]
    assert calls == []
    assert draft["basic"]["learning_stage"] == "大一"
    assert draft["basic"]["learning_basis"] == "零基础"
    assert "软件工程专业" in draft["basic"]["background"]
    assert draft["preferences"]["goal"] == "项目实战"
    assert draft["preferences"]["content_style"] == ["案例", "代码实操"]
    assert draft["global_traits"]["cognitive_preferences"]["example_based"]["source"] == "self_reported"
    assert draft["global_traits"]["cognitive_preferences"]["hands_on"]["source"] == "self_reported"
    assert [
        item["label"]
        for item in draft["global_traits"]["interest_directions"]
    ] == ["人工智能应用", "软件开发"]
    assert result["current_field"] == "preferred_difficulty"


def test_onboarding_completion_reply_summarizes_profile():
    profile = _profile()
    profile["basic"].update({
        "learning_stage": "大一",
        "learning_basis": "零基础",
        "background": "软件工程专业，学过 Python 爬虫",
    })
    profile["preferences"].update({
        "goal": "概念理解",
        "content_style": ["图解", "案例"],
        "preferred_difficulty": "基础",
        "tutoring_style": "引导式",
    })

    service = ProfileOnboardingService()
    result = service.advance(
        profile=profile,
        messages=[
            {"role": "assistant", "content": "最后补一个兴趣方向"},
            {"role": "user", "content": "人工智能应用和软件开发"},
        ],
    )

    assert result["completed"] is True
    assert "我整理好了" in result["reply"]
    assert "确认无误后保存" in result["reply"]
