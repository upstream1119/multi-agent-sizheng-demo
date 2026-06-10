import os
import re

from src.generator.llm_provider import get_llm_provider
from src.generator.template_generator import generate_answer_from_hits


TEMPLATE_MODE = "template"
LLM_MODE = "llm"
DEFAULT_PROVIDER = "stub"
MIN_CITATION_MATCH_SCORE = 0.08
BASELINE_FALLBACK_ANSWER = (
    "普通大模型通常会直接围绕问题给出概括性回答，"
    "但不会自动展示参考资料、具体出处和回答检查结果。"
)


def _resolve_generator_mode() -> str:
    mode = os.getenv("DACHUANG_GENERATOR_MODE", TEMPLATE_MODE).strip().lower()
    if mode == LLM_MODE:
        return LLM_MODE
    return TEMPLATE_MODE


def _format_prompt_citation(citation: dict) -> str:
    doc = citation.get("doc") or "未知文献"
    section = citation.get("section") or "未知章节"
    page = citation.get("page")
    page_text = "PDF 页码待复核" if page is None else f"PDF 页码 {page}"
    return f"{doc} / {section} / {page_text}"


def build_evidence_prompt(query: str, hybrid_hits: list[dict], max_hits: int = 3) -> str:
    evidence_lines = []
    for index, hit in enumerate(hybrid_hits[:max_hits], start=1):
        citation = hit.get("citation", {})
        evidence_lines.append(
            f"[{index}] 标题：{hit.get('title', '')}\n"
            f"正文：{hit.get('text', '')}\n"
            f"来源：{_format_prompt_citation(citation)}"
        )

    evidence_text = "\n\n".join(evidence_lines) or "无可用证据"
    return (
        "你是思政教育系统中的生成智能体。\n"
        "你只能依据给定证据回答，不能补充证据外内容。\n"
        "如果证据不足，请明确说明证据不足，不能编造 citation。\n\n"
        "输出要求：\n"
        "1. 用 2-4 段中文回答，语言自然，适合教学展示。\n"
        "2. 对事实判断和关键结论，在对应句末标注证据编号，如 [1]、[2]。\n"
        "3. 可以使用“根据《资料名称》的相关论述”等自然表达说明依据。\n"
        "4. 只能使用下方已经提供的证据编号，不能使用未提供的证据编号。\n"
        "5. 不要另写参考文献列表，系统会将编号与来源、章节和页码自动对应。\n\n"
        f"问题：{query}\n\n"
        f"证据：\n{evidence_text}"
    )


def _build_citations_used(hybrid_hits: list[dict], max_hits: int = 3) -> list[dict]:
    citations = []
    for hit in hybrid_hits[:max_hits]:
        citations.append(
            {
                "id": hit.get("id"),
                "title": hit.get("title"),
                "source": hit.get("source"),
                "citation": hit.get("citation", {}),
                "hybrid_score": hit.get("hybrid_score"),
            }
        )
    return citations


def _character_bigrams(text: str) -> set[str]:
    normalized = "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text or ""))
    return {
        normalized[index:index + 2]
        for index in range(max(0, len(normalized) - 1))
    }


def _citation_match_score(paragraph: str, hit: dict) -> float:
    paragraph_bigrams = _character_bigrams(paragraph)
    citation = hit.get("citation", {})
    evidence_text = " ".join(
        [
            hit.get("title", ""),
            hit.get("text", ""),
            citation.get("doc", ""),
            citation.get("section", ""),
        ]
    )
    evidence_bigrams = _character_bigrams(evidence_text)
    if not paragraph_bigrams or not evidence_bigrams:
        return 0.0
    overlap = paragraph_bigrams & evidence_bigrams
    return len(overlap) / min(len(paragraph_bigrams), len(evidence_bigrams))


def attach_grounded_citations(
    answer: str,
    hybrid_hits: list[dict],
    max_hits: int = 3,
) -> str:
    if not answer or not hybrid_hits:
        return answer

    hits = hybrid_hits[:max_hits]
    parts = re.split(r"(\n\s*\n)", answer)
    cited_parts = []
    for part in parts:
        paragraph = part.strip()
        if (
            not paragraph
            or re.fullmatch(r"\n\s*\n", part)
            or re.search(r"\[\d+\]", paragraph)
            or paragraph.startswith(("引用依据：", "引用来源："))
            or len(paragraph) < 12
        ):
            cited_parts.append(part)
            continue

        scores = [
            _citation_match_score(paragraph, hit)
            for hit in hits
        ]
        best_index = max(range(len(scores)), key=scores.__getitem__)
        if scores[best_index] < MIN_CITATION_MATCH_SCORE:
            cited_parts.append(part)
            continue

        trailing_space = part[len(part.rstrip()):]
        cited_parts.append(f"{part.rstrip()}[{best_index + 1}]{trailing_space}")

    return "".join(cited_parts)


def generate_baseline_answer(query: str) -> dict:
    prompt = (
        "你是一个普通通用大模型，请直接回答用户问题。\n"
        "本次回答不提供外部知识库证据，不进行引用溯源或内容规范审查。\n"
        "不要声称使用了未提供的文献、引用或页码。\n"
        "请用自然、简洁的中文回答。\n\n"
        f"问题：{query}"
    )
    provider_name = os.getenv("DACHUANG_LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
    provider = get_llm_provider(provider_name)
    provider_result = provider.generate(prompt)
    answer = provider_result.text.strip()
    if provider_result.status != "success" or not answer:
        answer = BASELINE_FALLBACK_ANSWER
    return {
        "answer": answer,
        "provider": provider_result.provider_name,
        "provider_status": provider_result.status,
    }


def generate_answer(query: str, hybrid_hits: list[dict]) -> dict:
    mode = _resolve_generator_mode()
    if mode == LLM_MODE:
        prompt = build_evidence_prompt(query, hybrid_hits)
        provider_name = os.getenv("DACHUANG_LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
        provider = get_llm_provider(provider_name)
        provider_result = provider.generate(prompt)

        generated = generate_answer_from_hits(query, hybrid_hits)
        if provider_result.status == "success" and provider_result.text.strip():
            generated["answer"] = attach_grounded_citations(
                provider_result.text.strip(),
                hybrid_hits,
            )
            generated["citations_used"] = _build_citations_used(hybrid_hits)
        generated["generator_mode"] = LLM_MODE
        generated["generator_provider"] = provider_result.provider_name
        generated["provider_status"] = provider_result.status
        generated["prompt_preview"] = prompt
        return generated

    generated = generate_answer_from_hits(query, hybrid_hits)
    generated["generator_mode"] = TEMPLATE_MODE
    return generated
