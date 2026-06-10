import html
import os

import streamlit as st

from demo_presenter import build_demo_view
from src.retriever.hybrid_retriever import retrieve


os.environ["DACHUANG_RETRIEVE_MODE"] = "mock"
os.environ["DACHUANG_LOCAL_MOCK_ACK"] = "1"
os.environ["DACHUANG_GENERATOR_MODE"] = "llm"
os.environ["DACHUANG_LLM_PROVIDER"] = "zhipu"

EXAMPLE_QUESTIONS = [
    "中国共产党思想政治教育史为什么重要？",
    "三湾改编对人民军队建设有什么意义？",
    "抗日战争时期党的干部教育为什么重要？",
]

SCENARIO_EXAMPLES = [
    {
        "label": "概念解释",
        "question": EXAMPLE_QUESTIONS[0],
        "desc": "解释课程中的核心概念，形成清晰易懂的回答。",
    },
    {
        "label": "历史事件分析",
        "question": EXAMPLE_QUESTIONS[1],
        "desc": "结合课程资料，分析历史事件的意义与影响。",
    },
    {
        "label": "教育实践总结",
        "question": EXAMPLE_QUESTIONS[2],
        "desc": "归纳特定时期的教育实践与主要特点。",
    },
]

LIVE_EXECUTION_TEMPLATE = [
    {
        "step": "01",
        "agent": "检索智能体",
        "task": "从固定知识库中召回相关证据。",
        "tool": "固定知识库检索工具 + KG-RAG 混合召回",
        "input": "用户问题、关键词实体、固定知识库",
        "output": "等待检索结果",
    },
    {
        "step": "02",
        "agent": "回答生成智能体",
        "task": "只依据已召回证据调用 GLM-4.5-Air 组织教学回答。",
        "tool": "GLM-4.5-Air API / 本地兜底生成器",
        "input": "用户问题、召回证据、citation 信息",
        "output": "等待生成结果",
    },
    {
        "step": "03",
        "agent": "溯源审查智能体",
        "task": "核验回答是否具备 citation 支撑。",
        "tool": "Citation 规则核验器",
        "input": "生成回答、citations_used",
        "output": "等待审查结果",
    },
    {
        "step": "04",
        "agent": "内容规范审查智能体",
        "task": "对表达边界和复核风险进行规则初筛。",
        "tool": "内容规范规则初筛器",
        "input": "生成回答、溯源审查结果",
        "output": "等待初筛结果",
    },
]

st.set_page_config(
    page_title="多智能体协同教学问答助手",
    page_icon="知",
    layout="wide",
    initial_sidebar_state="collapsed",
)

try:
    secret_api_key = st.secrets.get("ZHIPUAI_API_KEY", "")
except Exception:
    secret_api_key = ""
if secret_api_key and not os.getenv("ZHIPUAI_API_KEY"):
    os.environ["ZHIPUAI_API_KEY"] = secret_api_key

st.markdown(
    """
    <style>
    :root {
        --ink: #2f2925;
        --muted: #726761;
        --paper: #fbf8f1;
        --paper-deep: #f0e8da;
        --red: #8c1d28;
        --red-deep: #65151d;
        --gold: #b78b42;
        --line: rgba(101, 21, 29, 0.16);
    }

    .stApp {
        background:
            radial-gradient(circle at 92% 8%, rgba(183, 139, 66, 0.13), transparent 25rem),
            linear-gradient(180deg, #fbf8f1 0%, #f6f0e5 100%);
        color: var(--ink);
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"],
    #MainMenu {
        display: none;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    .hero {
        position: relative;
        overflow: hidden;
        padding: 2.3rem 2.5rem;
        border: 1px solid var(--line);
        border-radius: 24px;
        background: linear-gradient(135deg, rgba(255,255,255,.92), rgba(244,235,220,.88));
        box-shadow: 0 18px 50px rgba(73, 45, 32, 0.08);
    }

    .hero::after {
        content: "协同";
        position: absolute;
        right: 2rem;
        top: -.7rem;
        color: rgba(140, 29, 40, 0.055);
        font-size: 8rem;
        font-weight: 800;
        letter-spacing: .12em;
    }

    .eyebrow {
        color: var(--red);
        font-size: .82rem;
        font-weight: 700;
        letter-spacing: .2em;
    }

    .hero h1 {
        position: relative;
        z-index: 1;
        margin: .55rem 0 .6rem;
        color: var(--red-deep);
        font-size: clamp(2rem, 4.5vw, 3.5rem);
        line-height: 1.15;
        letter-spacing: .02em;
    }

    .hero p {
        position: relative;
        z-index: 1;
        max-width: 760px;
        margin: 0;
        color: var(--muted);
        font-size: 1.05rem;
        line-height: 1.85;
    }

    .badges {
        display: flex;
        flex-wrap: wrap;
        gap: .65rem;
        margin-top: 1.35rem;
    }

    .badge {
        padding: .46rem .8rem;
        border: 1px solid rgba(140, 29, 40, .18);
        border-radius: 999px;
        background: rgba(255,255,255,.62);
        color: var(--red-deep);
        font-size: .88rem;
        font-weight: 650;
    }

    .scenario-card,
    .console-card,
    .final-report-card,
    .work-log-card,
    .evidence-chain {
        border: 1px solid var(--line);
        border-radius: 16px;
        background: rgba(255,255,255,.78);
        box-shadow: 0 8px 22px rgba(73,45,32,.045);
    }

    .scenario-card {
        min-height: 7.2rem;
        margin-bottom: .65rem;
        padding: 1rem;
    }

    .scenario-label {
        color: var(--red-deep);
        font-size: .92rem;
        font-weight: 780;
    }

    .scenario-question {
        margin-top: .35rem;
        color: var(--ink);
        font-weight: 700;
        line-height: 1.55;
    }

    .scenario-desc {
        margin-top: .45rem;
        color: var(--muted);
        font-size: .84rem;
        line-height: 1.55;
    }

    .console-grid,
    .work-log-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .75rem;
        margin: .8rem 0 1.2rem;
    }

    .console-card {
        padding: .9rem 1rem;
    }

    .console-label {
        color: var(--muted);
        font-size: .78rem;
        font-weight: 700;
    }

    .console-value {
        margin-top: .35rem;
        color: var(--red-deep);
        font-weight: 780;
        line-height: 1.5;
    }

    .final-report-card,
    .evidence-chain {
        padding: 1rem 1.05rem;
    }

    .final-report-row {
        display: flex;
        justify-content: space-between;
        gap: .8rem;
        padding: .42rem 0;
        border-bottom: 1px solid rgba(140, 29, 40, .08);
        color: var(--muted);
        font-size: .9rem;
    }

    .final-report-row strong {
        color: var(--ink);
        text-align: right;
    }

    .final-report-recommendation {
        margin-top: .75rem;
        color: var(--red-deep);
        font-size: .92rem;
        line-height: 1.65;
        font-weight: 650;
    }

    .work-log-card {
        padding: .9rem 1rem;
        border-left: 5px solid rgba(140, 29, 40, .28);
    }

    .work-log-card.success { border-left-color: #4e8568; }
    .work-log-card.warning { border-left-color: #bd812e; }
    .work-log-card.danger { border-left-color: #a32b33; }

    .work-log-head {
        display: flex;
        justify-content: space-between;
        gap: .7rem;
        color: var(--ink);
        font-weight: 760;
    }

    .work-log-text {
        margin-top: .55rem;
        color: var(--muted);
        font-size: .88rem;
        line-height: 1.65;
    }

    .evidence-chain {
        margin-top: .85rem;
        border-left: 5px solid var(--gold);
    }

    .evidence-chain-title {
        color: var(--red-deep);
        font-weight: 760;
        margin-bottom: .45rem;
    }

    .evidence-chain-item {
        color: var(--muted);
        font-size: .92rem;
        line-height: 1.65;
    }

    .section-title {
        margin: 2.2rem 0 .3rem;
        color: var(--red-deep);
        font-size: 1.35rem;
        font-weight: 750;
    }

    .section-note {
        margin-bottom: 1rem;
        color: var(--muted);
        font-size: .94rem;
    }

    div.stButton > button {
        min-height: 3.1rem;
        border: 1px solid rgba(140, 29, 40, .2);
        border-radius: 12px;
        background: rgba(255,255,255,.78);
        color: var(--red-deep);
        font-weight: 650;
        box-shadow: 0 5px 16px rgba(75, 45, 30, .04);
    }

    div.stButton > button:hover {
        border-color: var(--red);
        color: var(--red);
        transform: translateY(-1px);
    }

    div[data-testid="stTextArea"] textarea {
        border: 1px solid rgba(140, 29, 40, .22);
        border-radius: 14px;
        background: rgba(255,255,255,.84);
        color: var(--ink);
        font-size: 1rem;
    }

    .answer-card, .decision-card {
        padding: 1.4rem 1.55rem;
        border: 1px solid var(--line);
        border-radius: 16px;
        background: rgba(255,255,255,.82);
        box-shadow: 0 8px 24px rgba(73,45,32,.05);
    }

    .answer-card {
        border-left: 5px solid var(--red);
        line-height: 1.9;
    }

    .comparison-card {
        height: 100%;
        padding: 1.15rem 1.25rem;
        border: 1px solid var(--line);
        border-radius: 18px;
        background: rgba(255,255,255,.82);
        box-shadow: 0 10px 28px rgba(73,45,32,.055);
    }

    .comparison-card.trusted {
        border-top: 5px solid #4e8568;
    }

    .comparison-card.baseline {
        border-top: 5px solid #9b918b;
    }

    .comparison-head {
        display: flex;
        justify-content: space-between;
        gap: .7rem;
        align-items: center;
        margin-bottom: .85rem;
    }

    .comparison-title {
        color: var(--red-deep);
        font-size: 1.12rem;
        font-weight: 780;
    }

    .comparison-status {
        padding: .28rem .55rem;
        border-radius: 999px;
        background: rgba(140, 29, 40, .07);
        font-size: .8rem;
        font-weight: 700;
    }

    .comparison-answer {
        min-height: 11rem;
        color: var(--ink);
        line-height: 1.85;
    }

    .capability-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: .55rem;
        margin-top: 1rem;
    }

    .capability-item {
        padding: .6rem .7rem;
        border: 1px solid rgba(140, 29, 40, .1);
        border-radius: 11px;
        background: rgba(250,247,240,.72);
    }

    .capability-label {
        color: var(--muted);
        font-size: .76rem;
        font-weight: 700;
    }

    .capability-value {
        margin-top: .2rem;
        color: var(--ink);
        font-size: .9rem;
        font-weight: 720;
    }

    .benefit-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: .8rem;
        margin: .85rem 0 1.25rem;
    }

    .benefit-card {
        padding: 1rem 1.05rem;
        border: 1px solid var(--line);
        border-radius: 15px;
        background: rgba(255,255,255,.78);
        text-align: center;
    }

    .benefit-index {
        width: 2.1rem;
        height: 2.1rem;
        display: grid;
        place-items: center;
        margin: 0 auto .55rem;
        border-radius: 999px;
        background: rgba(78, 133, 104, .12);
        color: #357052;
        font-weight: 800;
    }

    .benefit-title {
        color: var(--ink);
        font-weight: 760;
    }

    .benefit-text {
        margin-top: .35rem;
        color: var(--muted);
        font-size: .86rem;
        line-height: 1.6;
    }

    .agent-grid,
    .stage-grid,
    .report-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .8rem;
        margin: .8rem 0 1.2rem;
    }

    .agent-card,
    .report-card,
    .stage {
        padding: 1rem;
        border: 1px solid var(--line);
        border-radius: 14px;
        background: rgba(255,255,255,.72);
    }

    .agent-card {
        position: relative;
        min-height: 8.2rem;
    }

    .agent-card::before {
        content: "";
        position: absolute;
        top: 1rem;
        right: 1rem;
        width: .65rem;
        height: .65rem;
        border-radius: 999px;
        background: currentColor;
        opacity: .72;
    }

    .agent-name,
    .report-value,
    .stage-label {
        color: var(--ink);
        font-weight: 700;
    }

    .agent-task {
        margin-top: .65rem;
        color: var(--muted);
        font-size: .88rem;
        line-height: 1.65;
    }

    .agent-status,
    .report-label,
    .stage-status {
        margin-top: .3rem;
        font-size: .86rem;
    }

    .report-value {
        color: var(--red-deep);
        font-size: 1.35rem;
    }

    .flow-strip {
        display: flex;
        flex-wrap: wrap;
        gap: .5rem;
        align-items: center;
        margin: .85rem 0 1.15rem;
        color: var(--muted);
        font-size: .92rem;
    }

    .flow-node {
        padding: .4rem .65rem;
        border: 1px solid rgba(140, 29, 40, .16);
        border-radius: 999px;
        background: rgba(255,255,255,.68);
        color: var(--red-deep);
        font-weight: 650;
    }

    .execution-panel {
        display: grid;
        gap: .8rem;
        margin: .85rem 0 1.25rem;
    }

    .execution-step {
        display: grid;
        grid-template-columns: 4rem 1fr auto;
        gap: .85rem;
        align-items: start;
        padding: 1rem 1.05rem;
        border: 1px solid var(--line);
        border-left: 5px solid rgba(140, 29, 40, .36);
        border-radius: 15px;
        background: rgba(255,255,255,.78);
        box-shadow: 0 6px 18px rgba(73,45,32,.045);
    }

    .execution-step.running {
        border-left-color: var(--gold);
        background: rgba(255, 250, 238, .9);
    }

    .execution-step.success {
        border-left-color: #4e8568;
    }

    .execution-step.warning {
        border-left-color: #bd812e;
    }

    .execution-step.danger {
        border-left-color: #a32b33;
    }

    .execution-index {
        width: 3rem;
        height: 3rem;
        display: grid;
        place-items: center;
        border-radius: 999px;
        background: rgba(140, 29, 40, .08);
        color: var(--red-deep);
        font-weight: 800;
        letter-spacing: .04em;
    }

    .execution-agent {
        color: var(--ink);
        font-size: 1.02rem;
        font-weight: 760;
    }

    .execution-task {
        margin-top: .25rem;
        color: var(--muted);
        line-height: 1.65;
    }

    .execution-meta {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: .55rem;
        margin-top: .75rem;
    }

    .execution-chip {
        padding: .55rem .65rem;
        border: 1px solid rgba(140, 29, 40, .12);
        border-radius: 11px;
        background: rgba(255,255,255,.66);
    }

    .execution-chip-label {
        margin-bottom: .18rem;
        color: var(--red-deep);
        font-size: .76rem;
        font-weight: 760;
    }

    .execution-chip-value {
        color: var(--muted);
        font-size: .86rem;
        line-height: 1.55;
    }

    .execution-status {
        min-width: 5rem;
        padding: .32rem .55rem;
        border-radius: 999px;
        background: rgba(140, 29, 40, .07);
        text-align: center;
        font-size: .84rem;
        font-weight: 760;
    }

    .success { color: #357052; }
    .warning { color: #9a641c; }
    .danger { color: #a32b33; }
    .neutral { color: var(--muted); }

    .decision-card.success { border-left: 5px solid #4e8568; }
    .decision-card.warning { border-left: 5px solid #bd812e; }
    .decision-card.danger { border-left: 5px solid #a32b33; }

    .decision-title {
        margin-bottom: .35rem;
        color: var(--ink);
        font-size: 1.05rem;
        font-weight: 750;
    }

    .decision-reason {
        color: var(--muted);
        line-height: 1.7;
    }

    .footer-note {
        margin-top: 2.6rem;
        padding-top: 1rem;
        border-top: 1px solid var(--line);
        color: var(--muted);
        font-size: .84rem;
        text-align: center;
    }

    @media (max-width: 800px) {
        .block-container { padding: 1rem; }
        .hero { padding: 1.6rem 1.35rem; }
        .hero::after { display: none; }
        .agent-grid,
        .stage-grid,
        .report-grid,
        .console-grid,
        .work-log-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .execution-step { grid-template-columns: 1fr; }
        .execution-meta { grid-template-columns: 1fr; }
        .capability-grid { grid-template-columns: 1fr; }
        .benefit-grid { grid-template-columns: 1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_stage_cards(stages: list[dict]) -> None:
    cards = "".join(
        (
            f'<div class="stage">'
            f'<div class="stage-label">{html.escape(stage["label"])}</div>'
            f'<div class="stage-status {stage["tone"]}">{html.escape(stage["status"])}</div>'
            f"</div>"
        )
        for stage in stages
    )
    st.markdown(f'<div class="stage-grid">{cards}</div>', unsafe_allow_html=True)


def render_demo_console(report: dict) -> None:
    items = [
        ("当前任务", report["question"]),
        ("执行模式", report["mode"]),
        ("任务状态", "已完成"),
        ("可信等级", report["decision"]),
    ]
    cards = "".join(
        (
            f'<div class="console-card">'
            f'<div class="console-label">{html.escape(label)}</div>'
            f'<div class="console-value">{html.escape(value)}</div>'
            f"</div>"
        )
        for label, value in items
    )
    st.markdown(f'<div class="console-grid">{cards}</div>', unsafe_allow_html=True)


def render_comparison_card(item: dict, card_type: str) -> None:
    capabilities = "".join(
        (
            '<div class="capability-item">'
            f'<div class="capability-label">{html.escape(label)}</div>'
            f'<div class="capability-value">{html.escape(value)}</div>'
            "</div>"
        )
        for label, value in item.get("capabilities", [])
    )
    answer_html = html.escape(item.get("answer", "")).replace("\n", "<br>")
    st.markdown(
        (
            f'<div class="comparison-card {html.escape(card_type)}">'
            '<div class="comparison-head">'
            f'<div class="comparison-title">{html.escape(item["title"])}</div>'
            f'<div class="comparison-status {html.escape(item.get("tone", "neutral"))}">'
            f'{html.escape(item["status"])}</div>'
            "</div>"
            f'<div class="comparison-answer">{answer_html}</div>'
            f'<div class="capability-grid">{capabilities}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_benefits() -> None:
    items = [
        ("1", "先查资料", "回答前先从课程资料中查找相关内容。"),
        ("2", "标明出处", "给出资料名称、章节和页码，方便核对。"),
        ("3", "回答后检查", "生成后再次检查来源和表达是否稳妥。"),
    ]
    cards = "".join(
        (
            '<div class="benefit-card">'
            f'<div class="benefit-index">{index}</div>'
            f'<div class="benefit-title">{title}</div>'
            f'<div class="benefit-text">{text}</div>'
            "</div>"
        )
        for index, title, text in items
    )
    st.markdown(f'<div class="benefit-grid">{cards}</div>', unsafe_allow_html=True)


def render_evidence_chain(chain: list[str]) -> None:
    if not chain:
        return
    items = "".join(
        f'<div class="evidence-chain-item">[{index}] {html.escape(source)}</div>'
        for index, source in enumerate(chain, start=1)
    )
    st.markdown(
        (
            '<div class="evidence-chain">'
            '<div class="evidence-chain-title">本回答依据</div>'
            f"{items}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_final_report(report: dict) -> None:
    rows = [
        ("生成方式", report["generation_mode"]),
        ("召回证据", f'{report["evidence_count"]} 条'),
        ("引用来源", f'{report["citation_count"]} 条'),
        ("溯源审查", report["source_status"]),
        ("规范初筛", report["policy_status"]),
    ]
    row_html = "".join(
        (
            f'<div class="final-report-row">'
            f'<span>{html.escape(label)}</span>'
            f'<strong>{html.escape(value)}</strong>'
            f"</div>"
        )
        for label, value in rows
    )
    st.markdown(
        (
            '<div class="final-report-card">'
            f"{row_html}"
            f'<div class="final-report-recommendation">{html.escape(report["recommendation"])}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_work_logs(logs: list[dict]) -> None:
    cards = "".join(
        (
            f'<div class="work-log-card {html.escape(item["tone"])}">'
            f'<div class="work-log-head">'
            f'<span>{html.escape(item["agent"])}</span>'
            f'<span class="{html.escape(item["tone"])}">{html.escape(item["status"])}</span>'
            f"</div>"
            f'<div class="work-log-text">{html.escape(item["log"])}</div>'
            f"</div>"
        )
        for item in logs
    )
    st.markdown(f'<div class="work-log-grid">{cards}</div>', unsafe_allow_html=True)


def render_system_note() -> None:
    with st.expander("系统说明：受控流程式多智能体架构", expanded=False):
        st.markdown(
            """
            本系统将一次教学问答拆分为四个固定环节：检索、生成、溯源审查与内容规范审查。
            每个智能体只承担一个明确职责，最终形成带证据来源、审查结果和任务报告的回答。

            当前版本使用固定知识库进行离线检索，并通过 GLM-4.5-Air 或本地兜底生成器组织回答。
            规则型审查用于辅助展示和初筛，不替代人工复核与专业判断。
            """
        )


def ensure_view_defaults(view: dict) -> dict:
    view = dict(view or {})
    task_report = view.get("task_report", {})
    decision = view.get(
        "decision",
        {"label": "待确认", "tone": "neutral", "reason": "系统尚未形成最终结论。"},
    )
    view.setdefault("answer", "当前未形成回答。")
    view.setdefault("decision", decision)
    view.setdefault("agents", [])
    view.setdefault("execution_steps", [])
    view.setdefault("agent_outputs", [])
    view.setdefault("work_logs", [])
    view.setdefault("evidence", [])
    view.setdefault(
        "task_report",
        {
            "evidence_count": 0,
            "citation_count": 0,
            "source_status": "待确认",
            "policy_status": "待确认",
        },
    )
    view.setdefault(
        "evidence_chain",
        [item.get("source", "") for item in view["evidence"] if item.get("source")],
    )
    view.setdefault(
        "final_report",
        {
            "question": st.session_state.get("last_question", "当前问题待确认"),
            "mode": "固定知识库 + KG-RAG 检索 + GLM-4.5-Air/本地兜底 + 规则审查",
            "generation_mode": "GLM-4.5-Air/本地兜底",
            "evidence_count": task_report.get("evidence_count", 0),
            "citation_count": task_report.get("citation_count", 0),
            "source_status": task_report.get("source_status", "待确认"),
            "policy_status": task_report.get("policy_status", "待确认"),
            "decision": decision.get("label", "待确认"),
            "recommendation": "可作为阶段性教学辅助回答展示，建议保留证据边界说明。",
        },
    )
    view.setdefault(
        "comparison",
        {
            "baseline": {
                "title": "普通大模型",
                "answer": "请重新点击生成，以获得普通大模型的对比回答。",
                "status": "等待回答",
                "tone": "neutral",
                "capabilities": [
                    ("参考资料", "未提供"),
                    ("来源可查", "不支持"),
                    ("回答检查", "未进行"),
                ],
            },
            "trusted": {
                "title": "本系统",
                "answer": view["answer"],
                "status": "资料增强",
                "tone": "success",
                "capabilities": [
                    ("参考资料", f'{view["task_report"].get("evidence_count", 0)} 条'),
                    ("来源可查", f'{view["task_report"].get("citation_count", 0)} 条'),
                    (
                        "回答检查",
                        f'来源{view["task_report"].get("source_status", "待确认")}，'
                        f'内容{view["task_report"].get("policy_status", "待确认")}',
                    ),
                ],
            },
        },
    )
    baseline_comparison = view["comparison"].setdefault("baseline", {})
    trusted_comparison = view["comparison"].setdefault("trusted", {})
    baseline_comparison["title"] = "普通大模型"
    baseline_comparison["capabilities"] = [
        ("参考资料", "未提供"),
        ("来源可查", "不支持"),
        ("回答检查", "未进行"),
    ]
    trusted_comparison["title"] = "本系统"
    trusted_comparison["capabilities"] = [
        ("参考资料", f'{view["task_report"].get("evidence_count", 0)} 条'),
        ("来源可查", f'{view["task_report"].get("citation_count", 0)} 条'),
        (
            "回答检查",
            f'来源{view["task_report"].get("source_status", "待确认")}，'
            f'内容{view["task_report"].get("policy_status", "待确认")}',
        ),
    ]
    return view


def render_agent_workbench(agents: list[dict]) -> None:
    cards = "".join(
        (
            f'<div class="agent-card {agent["tone"]}">'
            f'<div class="agent-name">{html.escape(agent["name"])}</div>'
            f'<div class="agent-status {agent["tone"]}">{html.escape(agent["status"])}</div>'
            f'<div class="agent-task">{html.escape(agent["task"])}</div>'
            f"</div>"
        )
        for agent in agents
    )
    st.markdown(f'<div class="agent-grid">{cards}</div>', unsafe_allow_html=True)


def render_execution_monitor(steps: list[dict]) -> None:
    cards = []
    for step in steps:
        tone = html.escape(step.get("tone", "neutral"))
        cards.append(
            (
                f'<div class="execution-step {tone}">'
                f'<div class="execution-index">{html.escape(step["step"])}</div>'
                f'<div>'
                f'<div class="execution-agent">{html.escape(step["agent"])}</div>'
                f'<div class="execution-task">{html.escape(step["task"])}</div>'
                f'<div class="execution-meta">'
                f'<div class="execution-chip"><div class="execution-chip-label">调用工具</div>'
                f'<div class="execution-chip-value">{html.escape(step["tool"])}</div></div>'
                f'<div class="execution-chip"><div class="execution-chip-label">输入</div>'
                f'<div class="execution-chip-value">{html.escape(step["input"])}</div></div>'
                f'<div class="execution-chip"><div class="execution-chip-label">输出</div>'
                f'<div class="execution-chip-value">{html.escape(step["output"])}</div></div>'
                f'</div>'
                f'</div>'
                f'<div class="execution-status {tone}">{html.escape(step["status"])}</div>'
                f'</div>'
            )
        )
    st.markdown(f'<div class="execution-panel">{"".join(cards)}</div>', unsafe_allow_html=True)


def build_live_execution_steps(active_index: int) -> list[dict]:
    steps = []
    for index, item in enumerate(LIVE_EXECUTION_TEMPLATE):
        if index < active_index:
            status, tone, output = "已完成", "success", "已完成当前节点"
        elif index == active_index:
            status, tone, output = "运行中", "running", "正在处理"
        else:
            status, tone, output = "等待中", "neutral", item["output"]
        steps.append(
            {
                **item,
                "output": output,
                "status": status,
                "tone": tone,
            }
        )
    return steps


def render_agent_outputs(agent_outputs: list[dict]) -> None:
    for item in agent_outputs:
        label = f"{item['agent']} · {item['status']}"
        with st.expander(label, expanded=item.get("expanded", False)):
            st.markdown(f"**输出摘要：** {item['summary']}")
            for detail in item.get("details", []):
                st.markdown(f"**{detail['title']}**")
                for line in detail.get("lines", []):
                    st.markdown(f"- {line}")


def render_task_report(report: dict) -> None:
    items = [
        ("召回证据", f'{report["evidence_count"]} 条'),
        ("引用来源", f'{report["citation_count"]} 条'),
        ("溯源审查", report["source_status"]),
        ("规范初筛", report["policy_status"]),
    ]
    cards = "".join(
        (
            f'<div class="report-card">'
            f'<div class="report-value">{html.escape(value)}</div>'
            f'<div class="report-label">{html.escape(label)}</div>'
            f"</div>"
        )
        for label, value in items
    )
    st.markdown(f'<div class="report-grid">{cards}</div>', unsafe_allow_html=True)


def render_controlled_flow() -> None:
    st.markdown(
        """
        <div class="flow-strip">
            <span class="flow-node">用户任务</span>
            <span>→</span>
            <span class="flow-node">检索智能体</span>
            <span>→</span>
            <span class="flow-node">回答生成智能体</span>
            <span>→</span>
            <span class="flow-node">溯源审查智能体</span>
            <span>→</span>
            <span class="flow-node">内容规范审查智能体</span>
            <span>→</span>
            <span class="flow-node">任务报告</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result(view: dict) -> None:
    view = ensure_view_defaults(view)

    st.markdown('<div class="section-title">同一个问题，两种回答</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">左侧为普通大模型直接回答，右侧为本系统查阅资料并检查后的回答。</div>',
        unsafe_allow_html=True,
    )
    baseline_column, trusted_column = st.columns(2, gap="large")
    with baseline_column:
        render_comparison_card(view["comparison"]["baseline"], "baseline")
    with trusted_column:
        render_comparison_card(view["comparison"]["trusted"], "trusted")

    st.markdown('<div class="section-title">本系统多做了什么</div>', unsafe_allow_html=True)
    render_benefits()

    st.markdown('<div class="section-title">参考资料</div>', unsafe_allow_html=True)
    render_evidence_chain(view["evidence_chain"])
    if view["evidence"]:
        with st.expander("查看资料原文", expanded=False):
            for index, evidence in enumerate(view["evidence"], start=1):
                st.markdown(f"**资料 {index}：{evidence['title']}**")
                st.markdown(evidence["text"])
                st.caption(evidence["source"])
    else:
        st.info("当前资料库中没有找到足够内容，请尝试页面中的示例问题。")


st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">TRUSTWORTHY TEACHING ASSISTANT</div>
        <h1>可信教学问答助手</h1>
        <p>
            针对同一个问题，同时展示普通大模型回答和资料增强回答，
            并给出可核对的参考资料与出处。
        </p>
        <div class="badges">
            <span class="badge">回答对比</span>
            <span class="badge">资料支持</span>
            <span class="badge">来源可查</span>
            <span class="badge">回答检查</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-title">演示场景</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-note">选择一个场景，查看普通回答与资料增强回答的差异。</div>',
    unsafe_allow_html=True,
)

selected_question = None
example_columns = st.columns(3)
for column, scenario in zip(example_columns, SCENARIO_EXAMPLES):
    with column:
        st.markdown(
            (
                '<div class="scenario-card">'
                f'<div class="scenario-label">{html.escape(scenario["label"])}</div>'
                f'<div class="scenario-question">{html.escape(scenario["question"])}</div>'
                f'<div class="scenario-desc">{html.escape(scenario["desc"])}</div>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        if st.button(f"选择：{scenario['label']}", use_container_width=True):
            selected_question = scenario["question"]
            st.session_state["question"] = scenario["question"]

if "question" not in st.session_state:
    st.session_state["question"] = EXAMPLE_QUESTIONS[0]

st.markdown('<div class="section-title">自由提问</div>', unsafe_allow_html=True)
question = st.text_area(
    "请输入与中国共产党思想政治教育史相关的问题",
    key="question",
    height=110,
    label_visibility="collapsed",
)
analyze = st.button("生成并对比回答", type="primary", use_container_width=True)

if selected_question or analyze:
    active_question = selected_question or question.strip()
    if not active_question:
        st.warning("请先输入一个问题。")
    else:
        with st.status("正在生成两种回答...", expanded=True) as status:
            st.write("正在生成普通大模型回答...")
            st.write("正在查找相关资料并生成资料增强回答...")
            st.write("正在整理出处并检查回答...")
            st.session_state["result"] = build_demo_view(retrieve(active_question))
            st.session_state["last_question"] = active_question
            st.session_state["result"] = ensure_view_defaults(st.session_state["result"])
            status.update(label="两种回答已生成", state="complete", expanded=False)

if "result" in st.session_state:
    st.caption(f"本次问题：{st.session_state.get('last_question', '当前问题待确认')}")
    render_result(st.session_state["result"])

st.markdown(
    """
    <div class="footer-note">
        资料增强回答基于当前课程资料生成，仅用于教学辅助，不替代人工判断。
    </div>
    """,
    unsafe_allow_html=True,
)
