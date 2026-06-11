import os

import pytest

from demo_presenter import build_demo_view
from src.retriever.hybrid_retriever import retrieve


def test_example_question_produces_displayable_evidence():
    os.environ["DACHUANG_RETRIEVE_MODE"] = "mock"
    os.environ["DACHUANG_LOCAL_MOCK_ACK"] = "1"
    os.environ["DACHUANG_GENERATOR_MODE"] = "template"

    result = retrieve("抗日战争时期党的干部教育有什么特点？")
    view = build_demo_view(result)

    assert result["status"] == "success"
    assert view["answer"]
    assert len(view["evidence"]) >= 1
    assert len(view["stages"]) == 4
    assert view["decision"]["label"] in {"可展示", "需要复核"}


def test_llm_metadata_is_exposed_when_llm_mode_is_enabled():
    os.environ["DACHUANG_RETRIEVE_MODE"] = "mock"
    os.environ["DACHUANG_LOCAL_MOCK_ACK"] = "1"
    os.environ["DACHUANG_GENERATOR_MODE"] = "llm"
    os.environ["DACHUANG_LLM_PROVIDER"] = "zhipu"
    os.environ.pop("ZHIPUAI_API_KEY", None)

    result = retrieve("三湾改编对人民军队建设有什么意义？")
    view = build_demo_view(result)

    assert result["generator_mode"] == "llm"
    assert result["provider_status"] == "missing_api_key"
    assert result["baseline_provider_status"] == "missing_api_key"
    assert "不会自动展示参考资料" in result["baseline_answer"]
    assert view["provider_status"] == "missing_api_key"


def test_baseline_answer_retries_once_after_provider_failure(monkeypatch):
    attempts = []

    def fake_baseline(query):
        attempts.append(query)
        if len(attempts) == 1:
            return {
                "answer": "普通大模型回答暂时不可用，请稍后重试。",
                "provider": "fake",
                "provider_status": "api_error",
            }
        return {
            "answer": "重试后生成的普通大模型回答。",
            "provider": "fake",
            "provider_status": "success",
        }

    monkeypatch.setattr(
        "src.retriever.hybrid_retriever.generate_baseline_answer",
        fake_baseline,
    )
    monkeypatch.setenv("DACHUANG_RETRIEVE_MODE", "mock")
    monkeypatch.setenv("DACHUANG_LOCAL_MOCK_ACK", "1")
    monkeypatch.setenv("DACHUANG_GENERATOR_MODE", "template")

    result = retrieve("三湾改编对人民军队建设有什么意义？")

    assert len(attempts) == 2
    assert result["baseline_provider_status"] == "success"
    assert result["baseline_answer"] == "重试后生成的普通大模型回答。"
    assert result["answer"]


def test_retrieve_reports_workflow_progress_in_order(monkeypatch):
    events = []
    monkeypatch.setenv("DACHUANG_RETRIEVE_MODE", "mock")
    monkeypatch.setenv("DACHUANG_LOCAL_MOCK_ACK", "1")
    monkeypatch.setenv("DACHUANG_GENERATOR_MODE", "template")

    result = retrieve(
        "三湾改编对人民军队建设有什么意义？",
        progress_callback=lambda stage, status: events.append((stage, status)),
    )

    assert result["status"] == "success"
    assert events == [
        ("retrieval", "running"),
        ("retrieval", "completed"),
        ("generation", "running"),
        ("generation", "completed"),
        ("source_review", "running"),
        ("source_review", "completed"),
        ("content_review", "running"),
        ("content_review", "completed"),
        ("final_answer", "completed"),
    ]


def test_default_example_passes_review_in_template_fallback(monkeypatch):
    monkeypatch.setenv("DACHUANG_RETRIEVE_MODE", "mock")
    monkeypatch.setenv("DACHUANG_LOCAL_MOCK_ACK", "1")
    monkeypatch.setenv("DACHUANG_GENERATOR_MODE", "llm")
    monkeypatch.setenv("DACHUANG_LLM_PROVIDER", "zhipu")
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)

    result = retrieve("中国共产党思想政治教育史为什么重要？")

    assert result["provider_status"] == "missing_api_key"
    assert result["source_check"]["status"] == "pass"
    assert result["policy_check"]["status"] == "pass"
    assert result["final_decision"]["status"] == "approved"


@pytest.mark.parametrize(
    ("question", "expected_top_hit"),
    [
        ("中国共产党思想政治教育史为什么重要？", "chunk_szzjys_demo_002"),
        ("三湾改编对人民军队建设有什么意义？", "chunk_szzjys_demo_012"),
        ("抗日战争时期党的干部教育为什么重要？", "chunk_szzjys_demo_022"),
    ],
)
def test_teacher_examples_prioritize_relevant_evidence(question, expected_top_hit):
    os.environ["DACHUANG_RETRIEVE_MODE"] = "mock"
    os.environ["DACHUANG_LOCAL_MOCK_ACK"] = "1"

    result = retrieve(question)

    assert result["hybrid_hits"][0]["id"] == expected_top_hit
