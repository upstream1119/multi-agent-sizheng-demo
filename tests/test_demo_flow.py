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


@pytest.mark.parametrize(
    ("question", "expected_top_hit"),
    [
        ("中国共产党思想政治教育史为什么重要？", "chunk_szzjys_demo_001"),
        ("三湾改编对人民军队建设有什么意义？", "chunk_szzjys_demo_012"),
        ("抗日战争时期党的干部教育为什么重要？", "chunk_szzjys_demo_022"),
    ],
)
def test_teacher_examples_prioritize_relevant_evidence(question, expected_top_hit):
    os.environ["DACHUANG_RETRIEVE_MODE"] = "mock"
    os.environ["DACHUANG_LOCAL_MOCK_ACK"] = "1"

    result = retrieve(question)

    assert result["hybrid_hits"][0]["id"] == expected_top_hit
