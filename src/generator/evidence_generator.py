import os

from src.generator.llm_provider import get_llm_provider
from src.generator.template_generator import generate_answer_from_hits


TEMPLATE_MODE = "template"
LLM_MODE = "llm"
DEFAULT_PROVIDER = "stub"


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
        "2. 回答中必须包含“仅依据当前检索到的证据”这句话。\n"
        "3. 末尾必须列出“引用依据”，并写明来源、章节和 PDF 页码。\n\n"
        f"问题：{query}\n\n"
        f"证据：\n{evidence_text}"
    )


def generate_answer(query: str, hybrid_hits: list[dict]) -> dict:
    mode = _resolve_generator_mode()
    if mode == LLM_MODE:
        prompt = build_evidence_prompt(query, hybrid_hits)
        provider_name = os.getenv("DACHUANG_LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()
        provider = get_llm_provider(provider_name)
        provider_result = provider.generate(prompt)

        generated = generate_answer_from_hits(query, hybrid_hits)
        if provider_result.status == "success" and provider_result.text.strip():
            generated["answer"] = provider_result.text.strip()
        generated["generator_mode"] = LLM_MODE
        generated["generator_provider"] = provider_result.provider_name
        generated["provider_status"] = provider_result.status
        generated["prompt_preview"] = prompt
        return generated

    generated = generate_answer_from_hits(query, hybrid_hits)
    generated["generator_mode"] = TEMPLATE_MODE
    return generated
