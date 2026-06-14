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
            {"role": "user", "content": "我是本科第二年"},
        ],
        llm_config={"model": "mimo-v2.5"},
    )

    assert len(calls) == 1
    assert result["draft"]["basic"]["learning_stage"] == "大二"
