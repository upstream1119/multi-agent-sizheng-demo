import argparse
import csv
import json
import os
import re
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
    "hybrid_no_citation_enforcement",
    "hybrid_no_source_review",
    "hybrid_no_policy_review",
    "hybrid_no_trust_gate",
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
    "expected_hit_rank",
    "citation_count",
    "citation_precision_proxy",
    "grounded_paragraph_rate",
    "ungrounded_paragraph_count",
    "source_pass",
    "policy_pass",
    "final_approved",
    "unsupported_risk",
    "risky_output",
    "source_checked",
    "policy_checked",
    "trust_gate_enabled",
    "citation_enforcement_enabled",
    "source_status",
    "policy_status",
    "final_status",
    "answer_length",
    "answer_preview",
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


def _expected_hit_rank(expected_hit_ids: list[str], retrieved_hit_ids: list[str]) -> int:
    expected = set(expected_hit_ids)
    for index, hit_id in enumerate(retrieved_hit_ids, start=1):
        if hit_id in expected:
            return index
    return 0


def _join_ids(ids: list[str]) -> str:
    return "|".join(ids)


def _substantive_paragraphs(answer: str) -> list[str]:
    paragraphs = []
    for raw_paragraph in re.split(r"\n\s*\n", answer or ""):
        paragraph = raw_paragraph.strip()
        if len(paragraph) < 12:
            continue
        if paragraph.startswith(("引用依据：", "引用来源：")):
            continue
        if paragraph.startswith("以上回答仅依据当前检索到的证据生成"):
            continue
        paragraphs.append(paragraph)
    return paragraphs


def _grounding_metrics(answer: str, citation_count: int) -> dict:
    paragraphs = _substantive_paragraphs(answer)
    grounded_count = sum(1 for paragraph in paragraphs if re.search(r"\[\d+\]", paragraph))
    ungrounded_count = max(len(paragraphs) - grounded_count, 0)
    inline_citations = [int(index) for index in re.findall(r"\[(\d+)\]", answer or "")]
    invalid_citation_count = sum(
        1 for index in inline_citations if index < 1 or index > citation_count
    )
    if not paragraphs:
        grounded_rate = 0.0
    else:
        grounded_rate = round(grounded_count / len(paragraphs), 4)
    citation_precision = 1.0 if inline_citations and invalid_citation_count == 0 else 0.0
    if citation_count == 0:
        citation_precision = 0.0
    return {
        "citation_precision_proxy": citation_precision,
        "grounded_paragraph_rate": grounded_rate,
        "ungrounded_paragraph_count": ungrounded_count,
    }


def _answer_preview(answer: str, limit: int = 80) -> str:
    normalized = " ".join((answer or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip("，。；、 ") + "..."


def _strip_inline_citations(answer: str) -> str:
    return re.sub(r"\[\d+\]", "", answer or "").strip()


def _assumed_pass_source_check(citations_used: list[dict]) -> dict:
    return {
        "status": "pass",
        "issues": [],
        "checked_citation_count": len(citations_used),
    }


def _skipped_source_check(citations_used: list[dict]) -> dict:
    return {
        "status": "skipped",
        "issues": ["source review skipped for ablation"],
        "checked_citation_count": len(citations_used),
    }


def _skipped_policy_check() -> dict:
    return {
        "status": "skipped",
        "risk_types": [],
        "issues": ["policy review skipped for ablation"],
        "review_required": False,
        "max_severity": "none",
        "review_items": [],
        "suggestion": "",
    }


def _ungated_final_decision(answer: str) -> dict:
    return {
        "status": "output_without_gate" if answer else "no_answer",
        "can_output": bool(answer),
        "review_required": False,
        "reason": "trust gate skipped for ablation",
    }


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
        "expected_hit_rank": _expected_hit_rank(expected_ids, retrieved_ids),
        "answer_length": len(answer or ""),
        "answer_preview": _answer_preview(answer),
        "expert_fact_score": "",
        "expert_style_score": "",
        "expert_policy_score": "",
        "expert_preference": "",
    }


def _review_row(
    question: dict,
    system: str,
    hits: list[dict],
    generated: dict,
    *,
    source_checked: bool = True,
    policy_checked: bool = True,
    trust_gate_enabled: bool = True,
    citation_enforcement_enabled: bool = True,
) -> dict:
    answer = generated.get("answer", "")
    if not citation_enforcement_enabled:
        answer = _strip_inline_citations(answer)
    citations_used = generated.get("citations_used", [])
    source_check = (
        check_answer_sources(answer, citations_used)
        if source_checked
        else _skipped_source_check(citations_used)
    )
    source_check_for_policy = (
        source_check if source_checked else _assumed_pass_source_check(citations_used)
    )
    policy_check = (
        check_policy_risk(answer, citations_used, source_check_for_policy)
        if policy_checked
        else _skipped_policy_check()
    )
    final_decision = (
        build_final_decision(source_check_for_policy, policy_check)
        if trust_gate_enabled
        else _ungated_final_decision(answer)
    )

    row = _base_row(question, system, hits, answer)
    grounding = _grounding_metrics(answer, len(citations_used))
    unsupported_risk = int(
        (source_checked and source_check.get("status") != "pass")
        or not source_checked
        or (policy_checked and policy_check.get("review_required", False))
        or not policy_checked
    )
    can_output = bool(final_decision.get("can_output")) or final_decision.get("status") == "approved"
    row.update(
        {
            "citation_count": len(citations_used),
            **grounding,
            "source_pass": int(source_check.get("status") == "pass"),
            "policy_pass": int(policy_check.get("status") == "pass"),
            "final_approved": int(final_decision.get("status") == "approved"),
            "unsupported_risk": unsupported_risk,
            "risky_output": int(can_output and unsupported_risk),
            "source_checked": int(source_checked),
            "policy_checked": int(policy_checked),
            "trust_gate_enabled": int(trust_gate_enabled),
            "citation_enforcement_enabled": int(citation_enforcement_enabled),
            "source_status": source_check.get("status", ""),
            "policy_status": policy_check.get("status", ""),
            "final_status": final_decision.get("status", ""),
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
            **_grounding_metrics(baseline.get("answer", ""), 0),
            "source_pass": 0,
            "policy_pass": 0,
            "final_approved": 0,
            "unsupported_risk": 1,
            "risky_output": 1,
            "source_checked": 0,
            "policy_checked": 0,
            "trust_gate_enabled": 0,
            "citation_enforcement_enabled": 0,
            "source_status": "not_checked",
            "policy_status": "not_checked",
            "final_status": "not_approved",
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

    generated_variants = {}
    for system in ["vector_rag", "graph_rag", "hybrid_rag"]:
        hits = retrieval_variants[system]
        generated = generate_answer(question["question"], hits)
        generated_variants[system] = generated
        rows.append(_review_row(question, system, hits, generated))

    hybrid_hits = retrieval_variants["hybrid_rag"]
    hybrid_generated = generated_variants["hybrid_rag"]
    rows.append(
        _review_row(
            question,
            "hybrid_no_citation_enforcement",
            hybrid_hits,
            hybrid_generated,
            citation_enforcement_enabled=False,
        )
    )
    rows.append(
        _review_row(
            question,
            "hybrid_no_source_review",
            hybrid_hits,
            hybrid_generated,
            source_checked=False,
        )
    )
    rows.append(
        _review_row(
            question,
            "hybrid_no_policy_review",
            hybrid_hits,
            hybrid_generated,
            policy_checked=False,
        )
    )
    rows.append(
        _review_row(
            question,
            "hybrid_no_trust_gate",
            hybrid_hits,
            hybrid_generated,
            trust_gate_enabled=False,
        )
    )

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
            **_grounding_metrics(
                full_result.get("answer", ""),
                len(full_result.get("citations_used", [])),
            ),
            "source_pass": int(full_result.get("source_check", {}).get("status") == "pass"),
            "policy_pass": int(full_result.get("policy_check", {}).get("status") == "pass"),
            "final_approved": int(
                full_result.get("final_decision", {}).get("status") == "approved"
            ),
            "unsupported_risk": int(
                full_result.get("source_check", {}).get("status") != "pass"
                or full_result.get("policy_check", {}).get("review_required", False)
            ),
            "risky_output": int(
                full_result.get("final_decision", {}).get("can_output", False)
                and (
                    full_result.get("source_check", {}).get("status") != "pass"
                    or full_result.get("policy_check", {}).get("review_required", False)
                )
            ),
            "source_checked": 1,
            "policy_checked": 1,
            "trust_gate_enabled": 1,
            "citation_enforcement_enabled": 1,
            "source_status": full_result.get("source_check", {}).get("status", ""),
            "policy_status": full_result.get("policy_check", {}).get("status", ""),
            "final_status": full_result.get("final_decision", {}).get("status", ""),
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
            "risky_output_rate": round(
                sum(int(row["risky_output"]) for row in system_rows) / count,
                4,
            ),
            "grounded_paragraph_rate": round(
                sum(float(row["grounded_paragraph_rate"]) for row in system_rows) / count,
                4,
            ),
            "citation_precision_proxy": round(
                sum(float(row["citation_precision_proxy"]) for row in system_rows) / count,
                4,
            ),
        }
    failed_cases = [
        {
            "question_id": row["question_id"],
            "system": row["system"],
            "retrieval_hit_at_3": int(row["retrieval_hit_at_3"]),
            "source_status": row["source_status"],
            "policy_status": row["policy_status"],
            "final_status": row["final_status"],
        }
        for row in rows
        if int(row["retrieval_hit_at_3"]) == 0
        or row["source_status"] != "pass"
        or row["policy_status"] != "pass"
        or row["final_status"] != "approved"
    ]
    return {
        "question_count": question_count,
        "systems": SYSTEMS,
        "metrics": by_system,
        "failed_cases": failed_cases,
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
