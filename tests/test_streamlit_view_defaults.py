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
    assert view["comparison"]["baseline"]["status"] == "等待生成"
    assert view["comparison"]["trusted"]["answer"] == "旧 session 中缓存的回答。"
