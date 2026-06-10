from src.agents.agent_trace import build_final_decision
from src.reviewer.policy_checker import check_policy_risk


def test_grounded_answer_does_not_require_fixed_scope_statement():
    answer = (
        "中国共产党思想政治教育史是一门研究党的思想政治教育"
        "发生、发展历史及其规律的科学。[1]\n\n"
        "研究这段历史具有重要的理论和实践价值。[1]"
    )
    citations = [
        {
            "citation": {
                "doc": "中国共产党思想政治教育史",
                "section": "绪论",
                "page": 15,
            }
        }
    ]
    source_check = {
        "status": "pass",
        "issues": [],
        "checked_citation_count": 1,
    }

    policy_check = check_policy_risk(answer, citations, source_check)
    final_decision = build_final_decision(source_check, policy_check)

    assert policy_check["status"] == "pass"
    assert "missing_scope_statement" not in policy_check["risk_types"]
    assert final_decision["status"] == "approved"


def test_absolute_claim_still_requires_review():
    source_check = {
        "status": "pass",
        "issues": [],
        "checked_citation_count": 1,
    }
    policy_check = check_policy_risk(
        "这项工作已经彻底解决所有相关问题。[1]",
        [
            {
                "citation": {
                    "doc": "测试资料",
                    "section": "测试章节",
                    "page": 1,
                }
            }
        ],
        source_check,
    )

    assert policy_check["status"] == "warning"
    assert "unsupported_absolute_claim" in policy_check["risk_types"]
