from streamlit_app import ensure_view_defaults


def test_ensure_view_defaults_handles_legacy_session_view():
    legacy_view = {
        "answer": "旧 session 中缓存的回答。",
        "task_report": {
            "evidence_count": 2,
            "citation_count": 1,
            "source_status": "已完成",
            "policy_status": "建议复核",
        },
        "decision": {
            "label": "建议复核",
            "tone": "warning",
            "reason": "旧 session 中缓存的审查结论。",
        },
        "evidence": [
            {
                "title": "旧证据",
                "text": "旧证据内容",
                "source": "《中国共产党思想政治教育史》 · 旧章节 · 第 1 页",
            }
        ],
    }

    view = ensure_view_defaults(legacy_view)

    assert view["final_report"]["evidence_count"] == 2
    assert view["final_report"]["citation_count"] == 1
    assert view["final_report"]["decision"] == "建议复核"
    assert view["evidence_chain"] == ["《中国共产党思想政治教育史》 · 旧章节 · 第 1 页"]
    assert view["work_logs"] == []
    assert view["agent_outputs"] == []
    assert view["execution_steps"] == []
    assert view["comparison"]["baseline"]["status"] == "等待回答"
    assert "重新点击" not in view["comparison"]["baseline"]["answer"]
    assert view["comparison"]["trusted"]["answer"] == "旧 session 中缓存的回答。"
    assert view["source_cards"][0]["page"] == "可查看资料原文"


def test_ensure_view_defaults_preserves_source_review_warning():
    view = ensure_view_defaults(
        {
            "answer": "第一段没有来源编号。",
            "task_report": {
                "evidence_count": 1,
                "citation_count": 1,
                "source_status": "建议复核",
                "policy_status": "已完成",
            },
            "source_cards": [
                {
                    "index": 1,
                    "title": "测试资料",
                    "section": "测试章节",
                    "page": "第 1 页",
                }
            ],
        }
    )

    assert view["comparison"]["trusted"]["capabilities"][2] == (
        "回答检查",
        "部分内容待核验",
    )
