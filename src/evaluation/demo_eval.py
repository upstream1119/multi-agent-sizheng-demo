import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path

from src.agents.agent_trace import build_final_decision
from src.generator.evidence_generator import generate_answer, generate_baseline_answer
from src.retriever.hybrid_retriever import (
    extract_query_entities,
    fuse_results,
    retrieve,
    retrieve_graph,
    retrieve_vector,
    _load_demo_knowledge_base,
)
from src.reviewer.policy_checker import check_policy_risk
from src.reviewer.source_checker import check_answer_sources


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = REPO_ROOT / "eval" / "questions_demo.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "outputs" / "eval"
SYSTEMS = [
    "direct_llm",
    "vector_rag",
    "graph_rag",
    "hybrid_rag",
    "full_system",
]
CSV_FIELDS = [
    "question_id",
    "question",
    "category",
    "system",
    "expected_hit_ids",
    "retrieved_hit_ids",
    "retrieval_hit_at_3",
    "citation_count",
    "source_pass",
    "policy_pass",
    "final_approved",
    "unsupported_risk",
    "answer_length",
    "provider_status",
    "expert_fact_score",
    "expert_style_score",
    "expert_policy_score",
    "expert_preference",
]


def load_questions(dataset_path: str | Path) -> list[dict]:
    path = Path(dataset_path)
    if not path.is_absolute():
        path = REPO_ROOT / path

    questions = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def _hit_at_3(expected_hit_ids: list[str], retrieved_hit_ids: list[str]) -> int:
    return int(bool(set(expected_hit_ids) & set(retrieved_hit_ids[:3])))


def _join_ids(ids: list[str]) -> str:
    return "|".join(ids)


def _base_row(question: dict, system: str, hits: list[dict], answer: str) -> dict:
    expected_ids = question.get("expected_hit_ids", [])
    retrieved_ids = [hit.get("id", "") for hit in hits[:3]]
    return {
        "question_id": question["id"],
        "question": question["question"],
        "category": question.get("category", ""),
        "system": system,
        "expected_hit_ids": _join_ids(expected_ids),
        "retrieved_hit_ids": _join_ids(retrieved_ids),
        "retrieval_hit_at_3": _hit_at_3(expected_ids, retrieved_ids),
        "answer_length": len(answer or ""),
        "expert_fact_score": "",
        "expert_style_score": "",
        "expert_policy_score": "",
        "expert_preference": "",
    }


def _review_row(question: dict, system: str, hits: list[dict], generated: dict) -> dict:
    answer = generated.get("answer", "")
    citations_used = generated.get("citations_used", [])
    source_check = check_answer_sources(answer, citations_used)
    policy_check = check_policy_risk(answer, citations_used, source_check)
    final_decision = build_final_decision(source_check, policy_check)

    row = _base_row(question, system, hits, answer)
    row.update(
        {
            "citation_count": len(citations_used),
            "source_pass": int(source_check.get("status") == "pass"),
            "policy_pass": int(policy_check.get("status") == "pass"),
            "final_approved": int(final_decision.get("status") == "approved"),
            "unsupported_risk": int(
                source_check.get("status") != "pass"
                or policy_check.get("review_required", False)
            ),
            "provider_status": generated.get("provider_status", ""),
        }
    )
    return row


def _direct_llm_row(question: dict) -> dict:
    baseline = generate_baseline_answer(question["question"])
    row = _base_row(question, "direct_llm", [], baseline.get("answer", ""))
    row.update(
        {
            "citation_count": 0,
            "source_pass": 0,
            "policy_pass": 0,
            "final_approved": 0,
            "unsupported_risk": 1,
            "provider_status": baseline.get("provider_status", ""),
        }
    )
    return row


def _run_retrieval_variants(question: dict) -> dict[str, list[dict]]:
    query = question["question"]
    knowledge_base = _load_demo_knowledge_base()
    query_entities = extract_query_entities(query)
    vector_hits = retrieve_vector(query, query_entities)
    graph_hits = retrieve_graph(query_entities)
    hybrid_hits = fuse_results(vector_hits, graph_hits, knowledge_base)

    graph_full_hits = [
        {
            **next(item for item in knowledge_base if item["id"] == hit["id"]),
            **hit,
        }
        for hit in graph_hits
    ]

    return {
        "vector_rag": vector_hits,
        "graph_rag": graph_full_hits,
        "hybrid_rag": hybrid_hits,
    }


def evaluate_question(question: dict) -> list[dict]:
    rows = [_direct_llm_row(question)]
    retrieval_variants = _run_retrieval_variants(question)

    for system in ["vector_rag", "graph_rag", "hybrid_rag"]:
        hits = retrieval_variants[system]
        generated = generate_answer(question["question"], hits)
        rows.append(_review_row(question, system, hits, generated))

    full_result = retrieve(question["question"])
    full_row = _base_row(
        question,
        "full_system",
        full_result.get("hybrid_hits", []),
        full_result.get("answer", ""),
    )
    full_row.update(
        {
            "citation_count": len(full_result.get("citations_used", [])),
            "source_pass": int(full_result.get("source_check", {}).get("status") == "pass"),
            "policy_pass": int(full_result.get("policy_check", {}).get("status") == "pass"),
            "final_approved": int(
                full_result.get("final_decision", {}).get("status") == "approved"
            ),
            "unsupported_risk": int(
                full_result.get("source_check", {}).get("status") != "pass"
                or full_result.get("policy_check", {}).get("review_required", False)
            ),
            "provider_status": full_result.get("provider_status", ""),
        }
    )
    rows.append(full_row)
    return rows


def _summarize(rows: list[dict], question_count: int) -> dict:
    by_system = {}
    for system in SYSTEMS:
        system_rows = [row for row in rows if row["system"] == system]
        count = len(system_rows) or 1
        by_system[system] = {
            "retrieval_hit_at_3": round(
                sum(int(row["retrieval_hit_at_3"]) for row in system_rows) / count,
                4,
            ),
            "source_pass_rate": round(
                sum(int(row["source_pass"]) for row in system_rows) / count,
                4,
            ),
            "policy_pass_rate": round(
                sum(int(row["policy_pass"]) for row in system_rows) / count,
                4,
            ),
            "final_approved_rate": round(
                sum(int(row["final_approved"]) for row in system_rows) / count,
                4,
            ),
            "unsupported_risk_rate": round(
                sum(int(row["unsupported_risk"]) for row in system_rows) / count,
                4,
            ),
        }
    return {
        "question_count": question_count,
        "systems": SYSTEMS,
        "metrics": by_system,
        "notes": (
            "expert_* columns are intentionally left blank for later blind review; "
            "automatic metrics are smoke-test indicators, not final academic claims."
        ),
    }


def run_evaluation(
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    limit: int | None = None,
    timestamp: str | None = None,
) -> dict:
    os.environ["DACHUANG_RETRIEVE_MODE"] = "mock"
    os.environ["DACHUANG_LOCAL_MOCK_ACK"] = "1"
    os.environ.setdefault("DACHUANG_GENERATOR_MODE", "llm")
    os.environ.setdefault("DACHUANG_LLM_PROVIDER", "zhipu")

    questions = load_questions(dataset_path)
    if limit is not None:
        questions = questions[:limit]

    rows = []
    for question in questions:
        rows.extend(evaluate_question(question))

    output_path = Path(output_dir)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path
    output_path.mkdir(parents=True, exist_ok=True)

    run_id = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_path / f"demo_eval_{run_id}.csv"
    summary_path = output_path / f"demo_eval_{run_id}_summary.json"

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    summary = _summarize(rows, len(questions))
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return {
        "csv_path": csv_path,
        "summary_path": summary_path,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run demo baseline and ablation evaluation.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    result = run_evaluation(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        limit=args.limit,
    )
    print(f"CSV: {result['csv_path']}")
    print(f"Summary: {result['summary_path']}")


if __name__ == "__main__":
    main()
