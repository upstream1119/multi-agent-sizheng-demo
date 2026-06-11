import csv
import json

from src.evaluation.demo_eval import load_questions, run_evaluation
from src.retriever.hybrid_retriever import (
    _load_demo_knowledge_base,
    extract_query_entities,
    fuse_results,
    retrieve_graph,
    retrieve_vector,
)


def test_demo_eval_runs_offline_without_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    monkeypatch.setenv("DACHUANG_GENERATOR_MODE", "template")

    result = run_evaluation(
        dataset_path="eval/questions_demo.jsonl",
        output_dir=tmp_path,
        limit=2,
        timestamp="test",
    )

    assert result["summary_path"].exists()
    assert result["csv_path"].exists()

    with result["summary_path"].open("r", encoding="utf-8") as f:
        summary = json.load(f)

    assert summary["question_count"] == 2
    assert set(summary["systems"]) == {
        "direct_llm",
        "vector_rag",
        "graph_rag",
        "hybrid_rag",
        "hybrid_no_citation_enforcement",
        "hybrid_no_source_review",
        "hybrid_no_policy_review",
        "hybrid_no_trust_gate",
        "full_system",
    }

    with result["csv_path"].open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 18
    assert rows[0]["question_id"] == "q001"
    assert "retrieval_hit_at_3" in rows[0]
    assert "expected_hit_rank" in rows[0]
    assert "citation_precision_proxy" in rows[0]
    assert "grounded_paragraph_rate" in rows[0]
    assert "ungrounded_paragraph_count" in rows[0]
    assert "source_status" in rows[0]
    assert "policy_status" in rows[0]
    assert "final_status" in rows[0]
    assert "risky_output" in rows[0]
    assert "source_checked" in rows[0]
    assert "policy_checked" in rows[0]
    assert "trust_gate_enabled" in rows[0]
    assert "citation_enforcement_enabled" in rows[0]
    assert "answer_preview" in rows[0]
    assert "expert_fact_score" in rows[0]

    full_rows = [row for row in rows if row["system"] == "full_system"]
    assert any(float(row["grounded_paragraph_rate"]) >= 0 for row in full_rows)
    assert "grounded_paragraph_rate" in summary["metrics"]["full_system"]
    assert "risky_output_rate" in summary["metrics"]["full_system"]
    assert "failed_cases" in summary


def test_demo_question_set_has_enough_grounded_items():
    questions = load_questions("eval/questions_demo.jsonl")

    assert len(questions) >= 30
    assert len({question["id"] for question in questions}) == len(questions)
    assert all(question.get("expected_hit_ids") for question in questions)
    assert all(question.get("reference_note") for question in questions)


def test_extended_question_set_hybrid_retrieval_hits_gold_at_3():
    questions = load_questions("eval/questions_demo.jsonl")
    knowledge_base = _load_demo_knowledge_base()

    for question in questions:
        query = question["question"]
        query_entities = extract_query_entities(query)
        vector_hits = retrieve_vector(query, query_entities)
        graph_hits = retrieve_graph(query_entities)
        hybrid_hits = fuse_results(vector_hits, graph_hits, knowledge_base)
        retrieved_ids = {hit["id"] for hit in hybrid_hits[:3]}

        assert retrieved_ids & set(question["expected_hit_ids"]), question["id"]
