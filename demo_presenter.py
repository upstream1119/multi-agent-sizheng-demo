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
        "tool": "固定知识库检索工具 + KG-RAG 混合召回",
        "input": "用户问题、关键词实体、固定知识库",
    },
    "生成智能体": {
        "name": "回答生成智能体",
        "task": "只依据已召回证据调用 GLM-4.5-Air 组织教学回答。",
        "tool": "GLM-4.5-Air API / 本地兜底生成器",
        "input": "用户问题、召回证据、citation 信息",
    },
    "溯源审查智能体": {
        "name": "溯源审查智能体",
        "task": "核验回答是否具备 citation 支撑。",
        "tool": "Citation 规则核验器",
        "input": "生成回答、citations_used",
    },
    "政治红线审查智能体": {
        "name": "内容规范审查智能体",
        "task": "对表达边界和复核风险进行规则初筛。",
        "tool": "内容规范规则初筛器",
        "input": "生成回答、溯源审查结果",
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


def _build_step_output(role: str, result: dict) -> str:
    if role == "证据检索中枢":
        return f"召回 {len(result.get('hybrid_hits', []))} 条候选证据。"
    if role == "生成智能体":
        provider_status = result.get("provider_status") or "template"
        citation_count = len(result.get("citations_used", []))
        if provider_status == "success":
            return f"GLM-4.5-Air 生成回答，引用 {citation_count} 条来源。"
        if provider_status in {"missing_api_key", "api_error", "empty_response"}:
            return f"生成 API 状态：{provider_status}，已启用本地兜底回答。"
        return f"生成回答，引用 {citation_count} 条来源。"
    if role == "溯源审查智能体":
        checked_count = result.get("source_check", {}).get("checked_citation_count", 0)
        return f"完成 {checked_count} 条 citation 核验。"
    if role == "政治红线审查智能体":
        issues = result.get("policy_check", {}).get("issues", [])
        return f"完成内容规范初筛，发现 {len(issues)} 条复核提示。"
    return "完成当前流程节点。"


def build_demo_view(result: dict) -> dict:
    stages = []
    agents = []
    execution_steps = []
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
                "tool": "流程编排器",
                "input": "上一步输出",
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
        execution_steps.append(
            {
                "step": f"{len(execution_steps) + 1:02d}",
                "agent": agent_meta["name"],
                "task": agent_meta["task"],
                "tool": agent_meta["tool"],
                "input": agent_meta["input"],
                "output": _build_step_output(role, result),
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
        "execution_steps": execution_steps,
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
        "provider_status": result.get("provider_status"),
    }
