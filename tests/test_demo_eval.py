import csv
import json

from src.evaluation.demo_eval import run_evaluation


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
        "full_system",
    }

    with result["csv_path"].open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 10
    assert rows[0]["question_id"] == "q001"
    assert "retrieval_hit_at_3" in rows[0]
    assert "expert_fact_score" in rows[0]
