STAGE_LABELS = {
    "证据检索中枢": "证据检索",
    "生成智能体": "回答生成",
    "溯源审查智能体": "溯源审查",
    "政治红线审查智能体": "内容规范初筛",
}

AGENT_PRESENTATION = {
    "证据检索中枢": {
        "name": "检索智能体",
        "task": "从固定知识库中召回相关证据。",
    },
    "生成智能体": {
        "name": "回答生成智能体",
        "task": "只依据已召回证据组织教学回答。",
    },
    "溯源审查智能体": {
        "name": "溯源审查智能体",
        "task": "核验回答是否具备 citation 支撑。",
    },
    "政治红线审查智能体": {
        "name": "内容规范审查智能体",
        "task": "对表达边界和复核风险进行规则初筛。",
    },
}

STATUS_PRESENTATION = {
    "pass": ("已完成", "success"),
    "approved": ("可展示", "success"),
    "warning": ("建议复核", "warning"),
    "need_review": ("需要复核", "warning"),
    "needs_review": ("需要复核", "warning"),
    "no_evidence": ("证据不足", "warning"),
    "blocked": ("证据不足", "warning"),
    "fail": ("未通过", "danger"),
}


def _present_status(status: str) -> tuple[str, str]:
    return STATUS_PRESENTATION.get(status, ("处理中", "neutral"))


def _format_source(citation: dict) -> str:
    doc = citation.get("doc") or "来源待补充"
    section = citation.get("section") or "章节待补充"
    page = citation.get("page")
    page_text = "页码待复核" if page is None else f"第 {page} 页"
    return f"《{doc}》 · {section} · {page_text}"


def build_demo_view(result: dict) -> dict:
    stages = []
    agents = []
    for stage in result.get("agent_trace", []):
        status_text, tone = _present_status(stage.get("status", ""))
        role = stage.get("role")
        stages.append(
            {
                "label": STAGE_LABELS.get(role, role or "协同处理"),
                "status": status_text,
                "tone": tone,
            }
        )
        agent_meta = AGENT_PRESENTATION.get(
            role,
            {
                "name": role or "协同智能体",
                "task": "完成当前受控流程中的指定任务。",
            },
        )
        agents.append(
            {
                "name": agent_meta["name"],
                "task": agent_meta["task"],
                "status": status_text,
                "tone": tone,
            }
        )

    evidence = []
    for hit in result.get("hybrid_hits", [])[:3]:
        evidence.append(
            {
                "title": hit.get("title") or "未命名证据",
                "text": hit.get("text") or "",
                "source": _format_source(hit.get("citation", {})),
            }
        )

    final_decision = result.get("final_decision", {})
    decision_label, decision_tone = _present_status(final_decision.get("status", ""))
    source_label, _ = _present_status(result.get("source_check", {}).get("status", ""))
    policy_label, _ = _present_status(result.get("policy_check", {}).get("status", ""))

    return {
        "answer": result.get("answer") or "当前未形成回答。",
        "stages": stages,
        "agents": agents,
        "evidence": evidence,
        "task_report": {
            "evidence_count": len(result.get("hybrid_hits", [])),
            "citation_count": len(result.get("citations_used", [])),
            "source_status": source_label,
            "policy_status": policy_label,
        },
        "decision": {
            "label": decision_label,
            "tone": decision_tone,
            "reason": final_decision.get("reason") or "系统尚未形成最终结论。",
        },
        "source_check": result.get("source_check", {}),
        "policy_check": result.get("policy_check", {}),
    }
