import re


NO_EVIDENCE_STATUS = "no_evidence"
PASS_STATUS = "pass"
WARNING_STATUS = "warning"
FAIL_STATUS = "fail"


def _substantive_paragraphs(answer: str) -> list[str]:
    paragraphs = []
    for raw_paragraph in re.split(r"\n\s*\n", answer):
        paragraph = raw_paragraph.strip()
        if len(paragraph) < 12:
            continue
        if paragraph.startswith(("引用依据：", "引用来源：")):
            continue
        if paragraph.startswith("以上回答仅依据当前检索到的证据生成"):
            continue
        paragraphs.append(paragraph)
    return paragraphs


def check_answer_sources(answer: str, citations_used: list[dict]) -> dict:
    """
    溯源审查智能体最小原型：检查生成回答是否有 citation 支撑。
    当前只做规则检查，不调用外部大模型。
    """
    if not citations_used:
        return {
            "status": NO_EVIDENCE_STATUS,
            "issues": ["当前回答没有可用 citation，系统应保持不生成或提示证据不足。"],
            "checked_citation_count": 0,
        }

    issues = []
    inline_citations = [int(index) for index in re.findall(r"\[(\d+)\]", answer)]
    if not inline_citations:
        issues.append("回答正文没有标注证据编号，如 [1]。")
    else:
        substantive_paragraphs = _substantive_paragraphs(answer)
        for index, paragraph in enumerate(substantive_paragraphs, start=1):
            if not re.search(r"\[\d+\]", paragraph):
                issues.append(f"第 {index} 段缺少来源标注。")

    invalid_citations = sorted(
        {index for index in inline_citations if index < 1 or index > len(citations_used)}
    )
    for index in invalid_citations:
        issues.append(f"回答引用了不存在的证据编号 [{index}]。")

    for citation_item in citations_used:
        citation = citation_item.get("citation", {})
        hit_id = citation_item.get("id") or "未知证据"
        if not citation.get("doc"):
            issues.append(f"{hit_id} 缺少 citation.doc。")
        if not citation.get("section"):
            issues.append(f"{hit_id} 缺少 citation.section。")
        if citation.get("page") is None:
            issues.append(f"{hit_id} 的 citation.page 为空，需要后续页码复核。")

    status = PASS_STATUS
    if issues:
        status = WARNING_STATUS
    if any(
        "缺少 citation.doc" in issue
        or "缺少 citation.section" in issue
        or "不存在的证据编号" in issue
        for issue in issues
    ):
        status = FAIL_STATUS

    return {
        "status": status,
        "issues": issues,
        "checked_citation_count": len(citations_used),
    }
