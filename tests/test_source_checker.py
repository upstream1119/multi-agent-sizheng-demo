from src.reviewer.source_checker import check_answer_sources


def _citation(index: int) -> dict:
    return {
        "id": f"hit_{index:03d}",
        "citation": {
            "doc": "中国共产党思想政治教育史",
            "section": f"章节 {index}",
            "page": index,
        },
    }


def test_source_checker_accepts_valid_inline_citations():
    result = check_answer_sources(
        "资料表明，这一时期重视理论教育与实践结合。[1]",
        [_citation(1)],
    )

    assert result["status"] == "pass"
    assert result["issues"] == []


def test_source_checker_warns_when_inline_citation_is_missing():
    result = check_answer_sources(
        "资料表明，这一时期重视理论教育与实践结合。",
        [_citation(1)],
    )

    assert result["status"] == "warning"
    assert "回答正文没有标注证据编号" in result["issues"][0]


def test_source_checker_reports_specific_uncited_paragraph():
    result = check_answer_sources(
        "第一段内容具有来源支持。[1]\n\n第二段内容没有标注任何来源。",
        [_citation(1)],
    )

    assert result["status"] == "warning"
    assert "第 2 段缺少来源标注" in result["issues"][0]


def test_source_checker_rejects_unknown_inline_citation():
    result = check_answer_sources(
        "资料表明，这一时期重视理论教育与实践结合。[2]",
        [_citation(1)],
    )

    assert result["status"] == "fail"
    assert "不存在的证据编号 [2]" in result["issues"][0]
