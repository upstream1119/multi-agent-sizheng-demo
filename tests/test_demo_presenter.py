from demo_presenter import build_demo_view


def test_build_demo_view_formats_successful_result():
    result = {
        "answer": (
            "根据课程资料，延安时期重视理论教育与实践结合。[1]"
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

    assert view["answer"].startswith("根据课程资料")
    assert view["display_answer"] == "根据课程资料，延安时期重视理论教育与实践结合。[1]"
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
    assert view["comparison"]["trusted"]["answer"] == (
        "根据课程资料，延安时期重视理论教育与实践结合。[1]"
    )
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
    assert view["source_cards"][0]["index"] == 1


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


def test_comparison_marks_source_warning_as_pending_review():
    result = {
        "answer": "这是一段没有编号引用的回答。",
        "query": "测试问题",
        "hybrid_hits": [
            {
                "title": "测试资料",
                "text": "测试资料正文。",
                "citation": {"doc": "测试资料", "section": "测试章节", "page": 1},
            }
        ],
        "citations_used": [
            {
                "title": "测试资料",
                "citation": {"doc": "测试资料", "section": "测试章节", "page": 1},
            }
        ],
        "source_check": {"status": "warning", "issues": ["第 1 段缺少来源标注。"]},
        "policy_check": {"status": "pass", "issues": []},
        "final_decision": {"status": "approved", "reason": "测试"},
    }

    view = build_demo_view(result)

    assert view["comparison"]["trusted"]["capabilities"][2] == (
        "回答检查",
        "部分内容待核验",
    )
