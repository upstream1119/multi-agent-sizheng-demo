from demo_presenter import build_demo_view


def test_build_demo_view_formats_successful_result():
    result = {
        "answer": "基于证据形成的回答。",
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
        "policy_check": {"status": "pass", "issues": []},
        "final_decision": {
            "status": "approved",
            "reason": "溯源检查和政治红线初筛均通过。",
        },
    }

    view = build_demo_view(result)

    assert view["answer"] == "基于证据形成的回答。"
    assert view["stages"][0]["label"] == "证据检索"
    assert all(stage["tone"] == "success" for stage in view["stages"])
    assert view["evidence"][0]["source"] == (
        "《中国共产党思想政治教育史》 · 延安时期 · 第 126 页"
    )
    assert view["decision"]["label"] == "可展示"


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
