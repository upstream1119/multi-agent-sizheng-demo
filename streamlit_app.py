import html
import os
import time

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
        .report-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
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
    st.markdown('<div class="section-title">智能体工作台</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">系统采用受控流程式多智能体协同：每个智能体只负责固定环节，按顺序完成任务。</div>',
        unsafe_allow_html=True,
    )
    render_agent_workbench(view["agents"])
    render_controlled_flow()

    st.markdown('<div class="section-title">任务完成报告</div>', unsafe_allow_html=True)
    render_task_report(view["task_report"])

    st.markdown('<div class="section-title">可信回答</div>', unsafe_allow_html=True)
    answer_html = html.escape(view["answer"]).replace("\n", "<br>")
    st.markdown(f'<div class="answer-card">{answer_html}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">受控任务流</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-note">下方展示本次任务中各流程节点的执行状态。</div>',
        unsafe_allow_html=True,
    )
    render_stage_cards(view["stages"])

    st.markdown('<div class="section-title">参考依据</div>', unsafe_allow_html=True)
    if view["evidence"]:
        for index, evidence in enumerate(view["evidence"], start=1):
            with st.expander(f"证据 {index} · {evidence['title']}", expanded=index == 1):
                st.markdown(evidence["text"])
                st.caption(evidence["source"])
    else:
        st.info("当前固定知识库中没有检索到足够证据，请尝试示例问题或调整提问。")

    decision = view["decision"]
    st.markdown('<div class="section-title">审查结论</div>', unsafe_allow_html=True)
    st.markdown(
        (
            f'<div class="decision-card {decision["tone"]}">'
            f'<div class="decision-title">{html.escape(decision["label"])}</div>'
            f'<div class="decision-reason">{html.escape(decision["reason"])}</div>'
            f"</div>"
        ),
        unsafe_allow_html=True,
    )


st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">CONTROLLED MULTI-AGENT WORKFLOW</div>
        <h1>多智能体协同教学问答助手</h1>
        <p>
            面向思想政治教育场景，系统将一次提问拆分为固定任务流，
            由检索、生成、溯源审查与内容规范审查智能体分工完成。
        </p>
        <div class="badges">
            <span class="badge">受控流程式多智能体</span>
            <span class="badge">固定知识库</span>
            <span class="badge">证据可追溯</span>
            <span class="badge">任务报告可视化</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-title">一键示例</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-note">点击任一示例，系统将依次完成检索、生成、溯源审查与内容规范审查。</div>',
    unsafe_allow_html=True,
)

selected_question = None
example_columns = st.columns(3)
for column, example in zip(example_columns, EXAMPLE_QUESTIONS):
    if column.button(example, use_container_width=True):
        selected_question = example
        st.session_state["question"] = example

if "question" not in st.session_state:
    st.session_state["question"] = EXAMPLE_QUESTIONS[0]

st.markdown('<div class="section-title">自由提问</div>', unsafe_allow_html=True)
question = st.text_area(
    "请输入与中国共产党思想政治教育史相关的问题",
    key="question",
    height=110,
    label_visibility="collapsed",
)
analyze = st.button("启动多智能体协同分析", type="primary", use_container_width=True)

if selected_question or analyze:
    active_question = selected_question or question.strip()
    if not active_question:
        st.warning("请先输入一个问题。")
    else:
        with st.status("正在执行受控多智能体任务流...", expanded=True) as status:
            st.write("1. 检索智能体：正在从固定知识库召回相关证据。")
            time.sleep(0.25)
            st.write("2. 回答生成智能体：正在基于证据调用 GLM-4.5-Air 生成回答。")
            time.sleep(0.25)
            st.write("3. 溯源审查智能体：正在核验回答是否具备 citation 支撑。")
            time.sleep(0.25)
            st.write("4. 内容规范审查智能体：正在进行规则初筛并形成任务报告。")
            st.session_state["result"] = build_demo_view(retrieve(active_question))
            st.session_state["last_question"] = active_question
            provider_status = st.session_state["result"].get("provider_status")
            if provider_status and provider_status != "success":
                st.write(f"提示：生成 API 状态为 {provider_status}，系统已启用本地兜底回答。")
            status.update(label="多智能体任务流执行完成", state="complete")

if "result" in st.session_state:
    st.caption(f"本次问题：{st.session_state['last_question']}")
    render_result(st.session_state["result"])

st.markdown(
    """
    <div class="footer-note">
        本系统为阶段性教学演示版本。回答仅依据当前固定知识库生成，
        规则型审查结果用于辅助展示，不替代人工复核与专业判断。
    </div>
    """,
    unsafe_allow_html=True,
)
