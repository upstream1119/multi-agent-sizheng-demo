from demo_presenter import build_demo_view


def test_build_demo_view_formats_successful_result():
    result = {
        "answer": (
            "仅依据当前检索到的证据，基于证据形成的回答。\n\n"
            "引用依据：\n"
            "来源：中国共产党思想政治教育史 / 绪论 / PDF 页码 15"
        ),
        "baseline_answer": "普通大模型直接回答。",
        "baseline_provider_status": "success",
        "query": "延安时期思想政治教育有什么特点？",
        "hybrid_hits": [
            {
                "title": "延安时期的思想政治教育",
                "text": "延安时期重视理论教育与实践结合。",
                "citation": {
                    "doc": "中国共产党思想政治教育史",
                    "section": "延安时期",
                    "page": 126,
                },
                "hybrid_score": 0.91,
            }
        ],
        "agent_trace": [
            {"role": "证据检索中枢", "status": "pass"},
            {"role": "生成智能体", "status": "pass"},
            {"role": "溯源审查智能体", "status": "pass"},
            {"role": "政治红线审查智能体", "status": "pass"},
        ],
        "source_check": {"status": "pass", "issues": []},
        "policy_check": {"status": "pass", "issues": [], "risk_types": []},
        "final_decision": {
            "status": "approved",
            "reason": "溯源检查和政治红线初筛均通过。",
        },
    }

    view = build_demo_view(result)

    assert view["answer"].startswith("仅依据当前检索到的证据")
    assert view["display_answer"] == "基于证据形成的回答。"
    assert view["stages"][0]["label"] == "证据检索"
    assert view["agents"][0]["name"] == "检索智能体"
    assert view["agents"][0]["task"] == "从固定知识库中召回相关证据。"
    assert all(stage["tone"] == "success" for stage in view["stages"])
    assert view["evidence"][0]["source"] == (
        "《中国共产党思想政治教育史》 · 延安时期 · 第 126 页"
    )
    assert view["task_report"]["evidence_count"] == 1
    assert view["task_report"]["citation_count"] == 0
    assert view["task_report"]["source_status"] == "已完成"
    assert view["task_report"]["policy_status"] == "已完成"
    assert view["decision"]["label"] == "可展示"
    assert len(view["execution_steps"]) == 4
    assert view["execution_steps"][0]["agent"] == "检索智能体"
    assert view["execution_steps"][0]["tool"] == "固定知识库检索工具 + KG-RAG 混合召回"
    assert view["execution_steps"][0]["output"] == "召回 1 条候选证据。"
    assert view["execution_steps"][1]["agent"] == "回答生成智能体"
    assert view["execution_steps"][1]["tool"] == "GLM-4.5-Air API / 本地兜底生成器"
    assert view["execution_steps"][2]["output"] == "完成 0 条 citation 核验。"
    assert [item["agent"] for item in view["agent_outputs"]] == [
        "检索智能体",
        "回答生成智能体",
        "溯源审查智能体",
        "内容规范审查智能体",
    ]
    assert view["agent_outputs"][0]["expanded"] is True
    assert view["agent_outputs"][1]["expanded"] is True
    assert view["agent_outputs"][2]["expanded"] is False
    assert "hybrid_score" in view["agent_outputs"][0]["details"][0]["lines"][1]
    assert "回答生成结果" == view["agent_outputs"][1]["details"][1]["title"]
    assert len(view["work_logs"]) == 4
    assert view["work_logs"][0]["agent"] == "检索智能体"
    assert "召回 1 条候选证据" in view["work_logs"][0]["log"]
    assert view["evidence_chain"] == [
        "《中国共产党思想政治教育史》 · 延安时期 · 第 126 页"
    ]
    assert view["final_report"]["question"] == "延安时期思想政治教育有什么特点？"
    assert view["final_report"]["evidence_count"] == 1
    assert view["final_report"]["citation_count"] == 0
    assert view["final_report"]["decision"] == "可展示"
    assert view["comparison"]["baseline"]["answer"] == "普通大模型直接回答。"
    assert view["comparison"]["baseline"]["title"] == "普通大模型"
    assert view["comparison"]["baseline"]["capabilities"][0] == ("参考资料", "未提供")
    assert view["comparison"]["trusted"]["answer"] == "基于证据形成的回答。"
    assert view["comparison"]["trusted"]["title"] == "资料增强回答"
    assert view["comparison"]["trusted"]["capabilities"][0] == ("参考资料", "1 条")
    assert [label for label, _ in view["comparison"]["trusted"]["capabilities"]] == [
        "参考资料",
        "来源可查",
        "回答检查",
    ]
    assert view["comparison"]["trusted"]["capabilities"][2] == ("回答检查", "来源与内容已检查")
    assert view["source_cards"][0]["title"] == "中国共产党思想政治教育史"
    assert view["source_cards"][0]["page"] == "第 126 页"


def test_build_demo_view_handles_missing_evidence():
    result = {
        "answer": "当前知识库中没有检索到足够证据，暂不生成回答。",
        "hybrid_hits": [],
        "agent_trace": [],
        "source_check": {"status": "no_evidence", "issues": []},
        "policy_check": {"status": "need_review", "issues": []},
        "final_decision": {
            "status": "blocked",
            "reason": "缺少可用证据或溯源检查未通过。",
        },
    }

    view = build_demo_view(result)

    assert view["evidence"] == []
    assert view["decision"]["label"] == "证据不足"
    assert view["decision"]["tone"] == "warning"
